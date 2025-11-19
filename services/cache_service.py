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


class AmadeusCacheService:
    """MongoDB-based caching service for Amadeus API responses"""
    
    # Endpoint-specific TTLs (in hours)
    # Longer TTLs for static data, shorter for pricing
    ENDPOINT_TTL = {
        "/v1/reference-data/locations/hotels/by-city": 24 * 7,  # 7 days - hotel lists are relatively static
        "/v3/shopping/hotel-offers": 720,  # 
        "/v2/shopping/hotel-offers": 720,  #
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
        """Connect to MongoDB with graceful fallback"""
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
            print(f"MongoDB cache unavailable, falling back to direct API calls: {e}")
            self.enabled = False
            self.client = None
        except Exception as e:
            print(f"Error connecting to MongoDB cache: {e}")
            self.enabled = False
            self.client = None
    
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
        """
        if not self.enabled or self.collection is None:
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
                return None
            
            # Return cached response
            print(f"Cache HIT for endpoint: {endpoint}")
            return cached_doc.get("response_data")
            
        except Exception as e:
            print(f"Error retrieving from cache: {e}")
            # Graceful fallback - return None to proceed with API call
            return None
    
    async def set(self, endpoint: str, params: Optional[Dict[str, Any]], response_data: Dict[str, Any]):
        """
        Store API response in cache with expiration
        
        Args:
            endpoint: API endpoint path
            params: Request parameters
            response_data: API response data to cache
        """
        if not self.enabled or self.collection is None:
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
            
            print(f"Cache STORED for endpoint: {endpoint} (TTL: {ttl_hours}h)")
            
        except Exception as e:
            print(f"Error storing in cache: {e}")
            # Graceful fallback - continue without caching
    
    def is_available(self) -> bool:
        """Check if cache is available and enabled"""
        return self.enabled and self.collection is not None

