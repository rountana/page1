import os
import json
import hashlib
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

load_dotenv()


class MongoDBUnavailableError(Exception):
    """Raised when MongoDB cache is required but unavailable"""
    pass


class CacheMissError(Exception):
    """Raised when cache is enabled but data is not found in cache"""
    pass


class AmadeusCacheService:
    """MongoDB-based caching service for Amadeus API responses"""
    
    # Endpoint-specific TTLs (in hours)
    # Longer TTLs for static data, shorter for pricing
    ENDPOINT_TTL = {
        "/v1/reference-data/locations/hotels/by-city": 24 * 7,  # 7 days - hotel lists are relatively static
        "/v3/shopping/hotel-offers": 720,  # 
        "/v2/shopping/hotel-offers": 720,  #
        "/maps/api/place": 24 * 7 * 30,  # Google Places data is relatively static
        "/v1/security/oauth2/token": 1,  # tokens expire
        "default": 720  # 1 month default
    }
    
    def __init__(self, enable_cache: Optional[bool] = None):
        """
        Initialize cache service
        
        Args:
            enable_cache: If None, reads from AMADEUS_CACHE_ENABLED env var (default: True)
        """
        # Feature flag - can be disabled via environment variable
        if enable_cache is None:
            self.enabled = os.getenv("AMADEUS_CACHE_ENABLED", "true").lower() == "true"
        else:
            self.enabled = enable_cache
        
        self.client: Optional[MongoClient] = None
        self.db = None
        self.collection = None
        
        if self.enabled:
            self._connect()
    
    def _connect(self):
        """Connect to MongoDB - raises error if connection fails"""
        try:
            mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
            db_name = os.getenv("MONGODB_DB_NAME", "amadeus_cache")
            
            self.client = MongoClient(
                mongo_url,
                serverSelectionTimeoutMS=2000,  # 2 second timeout
                connectTimeoutMS=2000
            )
            
            # Test connection
            self.client.admin.command('ping')
            
            self.db = self.client[db_name]
            self.collection = self.db["api_responses"]
            
            # Create indexes for efficient queries
            self.collection.create_index("cache_key", unique=True)
            self.collection.create_index("expires_at", expireAfterSeconds=0)  # TTL index
            
            print("MongoDB cache connected successfully")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            error_msg = (
                f"MongoDB cache is unavailable. Please start MongoDB before running the application.\n"
                f"Connection error: {e}\n"
                f"To start MongoDB, run: ./start-mogodb.sh"
            )
            print(error_msg)
            raise MongoDBUnavailableError(error_msg) from e
        except Exception as e:
            error_msg = (
                f"MongoDB cache connection failed. Please start MongoDB before running the application.\n"
                f"Error: {e}\n"
                f"To start MongoDB, run: ./start-mogodb.sh"
            )
            print(error_msg)
            raise MongoDBUnavailableError(error_msg) from e
    
    def _normalize_params(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Normalize parameters for consistent cache keys
        - Sort keys
        - Convert values to strings for consistent hashing
        - Remove None values
        """
        if not params:
            return {}
        
        normalized = {}
        for key, value in sorted(params.items()):
            if value is not None:
                # Convert to string for consistent hashing
                if isinstance(value, (list, dict)):
                    normalized[key] = json.dumps(value, sort_keys=True)
                else:
                    normalized[key] = str(value)
        
        return normalized
    
    def _generate_cache_key(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate deterministic cache key from endpoint and normalized params
        
        Args:
            endpoint: API endpoint path
            params: Request parameters
            
        Returns:
            SHA256 hash of endpoint + normalized params
        """
        normalized_params = self._normalize_params(params)
        
        # Create a consistent string representation
        key_string = f"{endpoint}:{json.dumps(normalized_params, sort_keys=True)}"
        
        # Generate SHA256 hash for deterministic key
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def _get_ttl_hours(self, endpoint: str) -> float:
        """Get TTL in hours for a specific endpoint"""
        # Check exact match first
        if endpoint in self.ENDPOINT_TTL:
            return self.ENDPOINT_TTL[endpoint]
        
        # Check prefix match for versioned endpoints
        for cached_endpoint, ttl in self.ENDPOINT_TTL.items():
            if cached_endpoint != "default" and endpoint.startswith(cached_endpoint):
                return ttl
        
        # Return default TTL
        return self.ENDPOINT_TTL["default"]
    
    def _find_cache_doc(self, cache_key: str):
        """Helper method to find cache document (synchronous)"""
        if self.collection is None:
            return None
        return self.collection.find_one({"cache_key": cache_key})
    
    def _delete_cache_doc(self, cache_key: str):
        """Helper method to delete cache document (synchronous)"""
        if self.collection is None:
            return
        return self.collection.delete_one({"cache_key": cache_key})
    
    def _store_cache_doc(self, cache_key: str, cache_doc: Dict[str, Any]):
        """Helper method to store cache document (synchronous)"""
        if self.collection is None:
            return
        self.collection.replace_one(
            {"cache_key": cache_key},
            cache_doc,
            upsert=True
        )
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached response if available and not expired
        
        Args:
            endpoint: API endpoint path
            params: Request parameters
            
        Returns:
            Cached response data or None if not found/expired
            
        Raises:
            MongoDBUnavailableError: If MongoDB is not available
        """
        # Check if cache is required but unavailable
        if self.enabled and self.collection is None:
            raise MongoDBUnavailableError(
                "MongoDB cache is required but unavailable. Please start MongoDB before running the application.\n"
                "To start MongoDB, run: ./start-mogodb.sh"
            )
        
        # If cache is disabled, return None (this shouldn't happen if enabled=True, but handle gracefully)
        if not self.enabled:
            return None
        
        try:
            cache_key = self._generate_cache_key(endpoint, params)
            
            # Run MongoDB operation in thread pool (pymongo is synchronous)
            loop = asyncio.get_event_loop()
            cached_doc = await loop.run_in_executor(
                None,
                self._find_cache_doc,
                cache_key
            )
            
            if not cached_doc:
                # Log cache miss for Google Places endpoints
                if "/maps/api/place" in endpoint:
                    place_id = params.get("place_id", "unknown") if params else "unknown"
                    print(f"Cache MISS for Google Places endpoint: {endpoint} (place_id: {place_id})")
                else:
                    print(f"Cache MISS for endpoint: {endpoint}")
                return None
            
            # Check if expired (TTL index should handle this, but double-check)
            expires_at = cached_doc.get("expires_at")
            if expires_at and datetime.utcnow() > expires_at:
                # Remove expired entry
                await loop.run_in_executor(
                    None,
                    self._delete_cache_doc,
                    cache_key
                )
                # Log expired cache for Google Places
                if "/maps/api/place" in endpoint:
                    place_id = params.get("place_id", "unknown") if params else "unknown"
                    print(f"Cache EXPIRED for Google Places endpoint: {endpoint} (place_id: {place_id})")
                return None
            
            # Return cached response
            if "/maps/api/place" in endpoint:
                place_id = params.get("place_id", "unknown") if params else "unknown"
                print(f"Cache HIT for Google Places endpoint: {endpoint} (place_id: {place_id})")
            else:
                print(f"Cache HIT for endpoint: {endpoint}")
            return cached_doc.get("response_data")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            # MongoDB connection error - raise exception
            error_msg = (
                f"MongoDB cache connection lost during operation. Please ensure MongoDB is running.\n"
                f"Connection error: {e}\n"
                f"To start MongoDB, run: ./start-mogodb.sh"
            )
            raise MongoDBUnavailableError(error_msg) from e
        except Exception as e:
            # Re-raise MongoDBUnavailableError if that's what was raised
            if isinstance(e, MongoDBUnavailableError):
                raise
            # For other non-connection errors, log and return None to allow API call
            # This handles cases like query errors, but MongoDB is still available
            print(f"Error retrieving from cache (non-connection error): {e}")
            return None
    
    async def set(self, endpoint: str, params: Optional[Dict[str, Any]], response_data: Dict[str, Any]):
        """
        Store API response in cache with expiration
        
        Args:
            endpoint: API endpoint path
            params: Request parameters
            response_data: API response data to cache
            
        Raises:
            MongoDBUnavailableError: If MongoDB is not available
        """
        # Check if cache is required but unavailable
        if self.enabled and self.collection is None:
            raise MongoDBUnavailableError(
                "MongoDB cache is required but unavailable. Please start MongoDB before running the application.\n"
                "To start MongoDB, run: ./start-mogodb.sh"
            )
        
        # If cache is disabled, silently return (this shouldn't happen if enabled=True)
        if not self.enabled:
            return
        
        try:
            cache_key = self._generate_cache_key(endpoint, params)
            ttl_hours = self._get_ttl_hours(endpoint)
            expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
            
            # Store in MongoDB
            cache_doc = {
                "cache_key": cache_key,
                "endpoint": endpoint,
                "params": params,
                "response_data": response_data,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at,
                "ttl_hours": ttl_hours
            }
            
            # Run MongoDB operation in thread pool (pymongo is synchronous)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._store_cache_doc,
                cache_key,
                cache_doc
            )
            
            # Log cache write with more detail for Google Places
            if "/maps/api/place" in endpoint:
                place_id = params.get("place_id", "unknown") if params else "unknown"
                print(f"Cache STORED for Google Places endpoint: {endpoint} (place_id: {place_id}, TTL: {ttl_hours}h)")
            else:
                print(f"Cache STORED for endpoint: {endpoint} (TTL: {ttl_hours}h)")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            # MongoDB connection error - raise exception
            error_msg = (
                f"MongoDB cache connection lost during operation. Please ensure MongoDB is running.\n"
                f"Connection error: {e}\n"
                f"To start MongoDB, run: ./start-mogodb.sh"
            )
            raise MongoDBUnavailableError(error_msg) from e
        except Exception as e:
            # Re-raise MongoDBUnavailableError if that's what was raised
            if isinstance(e, MongoDBUnavailableError):
                raise
            # For other non-connection errors, log but don't abort - allow operation to continue
            # This handles cases like write errors, validation errors, etc. where MongoDB is still available
            print(f"Warning: Error storing in cache (non-connection error): {e}")
            print("Continuing without caching - API response will not be cached")
            # Don't raise - allow the API response to be returned even if caching fails
    
    def is_available(self) -> bool:
        """Check if cache is available and enabled"""
        return self.enabled and self.collection is not None

