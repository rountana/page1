import os
import httpx
from typing import Optional, List, Dict, Any
from datetime import date, timedelta
from dotenv import load_dotenv
from services.cache_service import AmadeusCacheService

load_dotenv()


class AmadeusService:
    """Service for interacting with Amadeus Self Service API"""
    
    def __init__(self):
        self.client_id = os.getenv("AMADEUS_CLIENT_ID")
        self.client_secret = os.getenv("AMADEUS_CLIENT_SECRET")
        self.env = os.getenv("AMADEUS_ENV", "test")
        
        # Base URLs based on environment
        if self.env == "test":
            self.base_url = "https://test.api.amadeus.com"
        else:
            self.base_url = "https://api.amadeus.com"
        
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[float] = None
        
        # Cache for hotels by city code
        self.hotel_cache: Dict[str, List[Dict[str, Any]]] = {}
        
        # Initialize MongoDB cache service
        self.cache_service = AmadeusCacheService()
        
    async def _get_access_token(self) -> str:
        """Get OAuth 2.0 access token using client credentials flow"""
        # Check if we have a valid token
        import time
        if self.access_token and self.token_expires_at and time.time() < self.token_expires_at:
            return self.access_token
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Amadeus API credentials not configured. Set AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET in .env")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/security/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data["access_token"]
            # Set expiration time (subtract 60 seconds for safety)
            expires_in = data.get("expires_in", 1800)
            self.token_expires_at = time.time() + expires_in - 60
            return self.access_token
    
    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make authenticated request to Amadeus API with MongoDB caching
        
        Args:
            endpoint: API endpoint path (e.g., "/v1/reference-data/locations/hotels/by-city")
            params: Request parameters
            
        Returns:
            API response data
        """
        # Check cache first (if enabled and available)
        cached_response = await self.cache_service.get(endpoint, params)
        if cached_response is not None:
            print(f"Cache HIT for endpoint: {endpoint} with params: {params}")
            return cached_response
        
        # Cache miss - make API request
        print(f"Cache MISS for endpoint: {endpoint}, making API request...")
        token = await self._get_access_token()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json"
                }
            )
            data = response.json()
            
            # Check for errors in the JSON response body
            if "errors" in data and len(data["errors"]) > 0:
                error = data["errors"][0]
                status_code = error.get("status", 500)
                detail = error.get("detail", "Unknown error")
                raise httpx.HTTPStatusError(
                    f"Amadeus API error: {detail}",
                    request=response.request,
                    response=response
                )
            
            # Store successful response in cache
            await self.cache_service.set(endpoint, params, data)
            
            return data
    
    async def _fetch_hotels_by_city(self, city_code: str) -> List[Dict[str, Any]]:
        """
        Fetch hotels in a city using Hotel List API
        Reference: https://developers.amadeus.com/self-service/category/hotels/api-doc/hotel-list/api-reference
        
        Args:
            city_code: IATA city code (e.g., "NYC", "PAR")
        
        Returns:
            List of hotel dictionaries with basic information
        """
        try:
            params = {
                "cityCode": city_code,
                "radius": 5,
                "radiusUnit": "KM",
                "hotelSource": "ALL"
            }
            
            data = await self._make_request("/v1/reference-data/locations/hotels/by-city", params)
            
            hotels = []
            if "data" in data:
                for hotel_data in data["data"]:
                    hotels.append({
                        "hotel_id": hotel_data.get("hotelId", ""),
                        "name": hotel_data.get("name", "Unknown Hotel"),
                        "geo_code": hotel_data.get("geoCode", {}),
                        "address": hotel_data.get("address", {}),
                        "raw_data": hotel_data
                    })
            
            return hotels
            
        except Exception as e:
            print(f"Error fetching hotels by city: {e}")
            return []
    
    async def _fetch_hotel_offers(
        self, 
        hotel_ids: List[str], 
        check_in: date, 
        check_out: date, 
        adults: int = 1
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch hotel offers for multiple hotels using Hotel Search API
        Reference: https://developers.amadeus.com/self-service/category/hotels/api-doc/hotel-search/api-reference
        
        Args:
            hotel_ids: List of hotel IDs
            check_in: Check-in date
            check_out: Check-out date
            adults: Number of adults
        
        Returns:
            Dictionary mapping hotel_id to hotel data with offers
        """
        # Amadeus API allows up to 10 hotel IDs per request
        batch_size = 10
        all_hotels = {}
        
        for i in range(0, len(hotel_ids), batch_size):
            batch = hotel_ids[i:i + batch_size]
            
            try:
                params = {
                    "hotelIds": ",".join(batch),
                    "checkInDate": check_in.isoformat(),
                    "checkOutDate": check_out.isoformat(),
                    "adults": adults
                }
                
                data = await self._make_request("/v3/shopping/hotel-offers", params)
                
                if "data" in data:
                    for hotel_data in data["data"]:
                        hotel_id = hotel_data.get("hotel", {}).get("hotelId", "")
                        if hotel_id:
                            all_hotels[hotel_id] = hotel_data
                            
            except Exception as e:
                print(f"Error fetching offers for hotel batch: {e}")
                continue
        
        return all_hotels
    
    async def search_hotels(
        self,
        city_code: str,
        check_in: date,
        check_out: date,
        adults: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Search for hotels using a two-step process:
        1. Fetch hotels in city using Hotel List API (cached)
        2. Fetch offers for each hotel using Hotel Search API
        
        Args:
            city_code: IATA city code (e.g., "NYC", "PAR")
            check_in: Check-in date
            check_out: Check-out date
            adults: Number of adults
        
        Returns:
            List of hotel data dictionaries with offers
        """
        try:
            # Calculate number of nights
            nights = (check_out - check_in).days
            
            # Step 1: Get hotels in city (use cache if available)
            if city_code not in self.hotel_cache:
                print(f"Fetching hotels for city: {city_code}")
                hotels_list = await self._fetch_hotels_by_city(city_code)
                self.hotel_cache[city_code] = hotels_list
                print(f"Cached {len(hotels_list)} hotels for {city_code}")
            else:
                print(f"Using cached hotels for {city_code}")
                hotels_list = self.hotel_cache[city_code]
            
            if not hotels_list:
                return []
            
            # Step 2: Get hotel IDs and fetch offers
            hotel_ids = [hotel["hotel_id"] for hotel in hotels_list if hotel.get("hotel_id")]
            
            print(f"Fetching offers for {len(hotel_ids)} hotels...")
            hotel_offers = await self._fetch_hotel_offers(hotel_ids, check_in, check_out, adults)
            print(f"found {len(hotel_offers)} offers")
            # Step 3: Combine hotel list data with offers
            hotels = []
            for hotel_info in hotels_list:
                hotel_id = hotel_info["hotel_id"]
                
                # If we have offers for this hotel, use that data
                if hotel_id in hotel_offers:
                    hotel = self._parse_hotel_data(
                        hotel_offers[hotel_id], 
                        check_in, 
                        check_out, 
                        nights
                    )
                    if hotel:
                        hotels.append(hotel)
                else:
                    # If no offers, create basic hotel entry without pricing
                    hotel = self._parse_hotel_from_list(hotel_info, check_in, check_out, nights)
                    if hotel:
                        hotels.append(hotel)
            
            print(f"Returning {len(hotels)} hotels with offers")
            return hotels
            
        except Exception as e:
            raise Exception(f"Error searching hotels: {str(e)}")
    
    def _parse_hotel_data(self, hotel_data: Dict[str, Any], check_in: date, check_out: date, nights: int) -> Optional[Dict[str, Any]]:
        """Parse Amadeus hotel data into our format"""
        try:
            hotel_info = hotel_data.get("hotel", {})
            hotel_id = hotel_info.get("hotelId", "")
            name = hotel_info.get("name", "Unknown Hotel")
            
            # Get images
            images = []
            if "media" in hotel_info:
                for media in hotel_info["media"]:
                    if media.get("category") == "EXTERIOR" or media.get("category") == "ROOM":
                        images.append({
                            "url": media.get("uri", ""),
                            "category": media.get("category", "")
                        })
            
            # Get address
            address = ""
            if "address" in hotel_info:
                addr = hotel_info["address"]
                address_parts = [
                    addr.get("lines", []),
                    addr.get("cityName", ""),
                    addr.get("countryCode", "")
                ]
                address = ", ".join(filter(None, [item for sublist in address_parts for item in (sublist if isinstance(sublist, list) else [sublist])]))
            
            # Get price from offers
            daily_price = None
            total_price = None
            currency = "USD"
            
            if "offers" in hotel_data and len(hotel_data["offers"]) > 0:
                offer = hotel_data["offers"][0]
                if "price" in offer:
                    price_info = offer["price"]
                    total_price = float(price_info.get("total", 0))
                    currency = price_info.get("currency", "USD")
                    if nights > 0:
                        daily_price = total_price / nights
            
            # If no price in offers, use default
            if daily_price is None:
                daily_price = 100.0  # Default fallback
                total_price = daily_price * nights
            
            return {
                "hotel_id": hotel_id,
                "name": name,
                "images": images,
                "address": address,
                "daily_price": daily_price,
                "total_price": total_price,
                "currency": currency,
                "rating": hotel_info.get("rating", None),
                "raw_data": hotel_data  # Store raw data for details page
            }
        except Exception as e:
            print(f"Error parsing hotel data: {e}")
            return None
    
    def _parse_hotel_from_list(
        self, 
        hotel_info: Dict[str, Any], 
        check_in: date, 
        check_out: date, 
        nights: int
    ) -> Optional[Dict[str, Any]]:
        """Parse hotel data from hotel list API (when no offers available)"""
        try:
            hotel_id = hotel_info.get("hotel_id", "")
            name = hotel_info.get("name", "Unknown Hotel")
            
            # Get address
            address = ""
            addr = hotel_info.get("address", {})
            if addr:
                address_parts = [
                    addr.get("lines", []),
                    addr.get("cityName", ""),
                    addr.get("countryCode", "")
                ]
                address = ", ".join(filter(None, [item for sublist in address_parts for item in (sublist if isinstance(sublist, list) else [sublist])]))
            
            # No pricing available without offers
            return {
                "hotel_id": hotel_id,
                "name": name,
                "images": [],  # Hotel list API doesn't include images
                "address": address,
                "daily_price": None,
                "total_price": None,
                "currency": "USD",
                "rating": None,
                "raw_data": hotel_info.get("raw_data", {})
            }
        except Exception as e:
            print(f"Error parsing hotel from list: {e}")
            return None
    
    async def get_hotel_details(
        self, 
        hotel_id: str,
        check_in: Optional[date] = None,
        check_out: Optional[date] = None,
        adults: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific hotel
        
        Args:
            hotel_id: Hotel ID from Amadeus
            check_in: Check-in date (required for hotel-offers endpoint)
            check_out: Check-out date (required for hotel-offers endpoint)
            adults: Number of adults
        
        Returns:
            Hotel details dictionary
        """
        try:
            # Default to dates 30 days from now if not provided
            if not check_in or not check_out:
                from datetime import timedelta
                check_in = check_in or date.today() + timedelta(days=30)
                check_out = check_out or check_in + timedelta(days=1)
            
            # Use Hotel Details API - requires dates for hotel-offers endpoint
            params = {
                "hotelIds": hotel_id,
                "checkInDate": check_in.isoformat(),
                "checkOutDate": check_out.isoformat(),
                "adults": adults
            }
            
            data = await self._make_request("/v2/shopping/hotel-offers", params)
            
            if "data" in data and len(data["data"]) > 0:
                hotel_data = data["data"][0]
                return self._parse_hotel_details(hotel_data)
            
            return None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise Exception(f"Amadeus API error: {e.response.status_code}")
        except Exception as e:
            raise Exception(f"Error getting hotel details: {str(e)}")
    
    def _parse_hotel_details(self, hotel_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse detailed hotel information"""
        hotel_info = hotel_data.get("hotel", {})
        hotel_id = hotel_info.get("hotelId", "")
        name = hotel_info.get("name", "Unknown Hotel")
        
        # Description
        description = hotel_info.get("description", {}).get("text", "")
        
        # Address
        address = ""
        if "address" in hotel_info:
            addr = hotel_info["address"]
            address_parts = [
                addr.get("lines", []),
                addr.get("cityName", ""),
                addr.get("countryCode", "")
            ]
            address = ", ".join(filter(None, [item for sublist in address_parts for item in (sublist if isinstance(sublist, list) else [sublist])]))
        
        # Images
        images = []
        if "media" in hotel_info:
            for media in hotel_info["media"]:
                images.append({
                    "url": media.get("uri", ""),
                    "category": media.get("category", "")
                })
        
        # Rooms and facilities from offers
        rooms = []
        facilities = set()
        
        if "offers" in hotel_data:
            for offer in hotel_data["offers"]:
                room_type = offer.get("room", {}).get("type", "Standard Room")
                room_description = offer.get("room", {}).get("description", {}).get("text", "")
                
                # Room facilities
                room_facilities = []
                if "room" in offer and "amenities" in offer["room"]:
                    for amenity in offer["room"]["amenities"]:
                        facilities.add(amenity.get("description", ""))
                        room_facilities.append({
                            "name": amenity.get("description", ""),
                            "description": amenity.get("description", "")
                        })
                
                # Price
                price_info = offer.get("price", {})
                total_price = float(price_info.get("total", 0))
                currency = price_info.get("currency", "USD")
                
                rooms.append({
                    "type": room_type,
                    "description": room_description,
                    "facilities": room_facilities,
                    "price": {
                        "total": total_price,
                        "currency": currency
                    },
                    "max_occupancy": offer.get("guests", {}).get("adults", 2)
                })
        
        # Hotel facilities
        hotel_facilities_list = []
        if "amenities" in hotel_info:
            for amenity in hotel_info["amenities"]:
                facilities.add(amenity.get("description", ""))
                hotel_facilities_list.append(amenity.get("description", ""))
        
        # Price (from first offer)
        daily_price = None
        total_price = None
        currency = "USD"
        if "offers" in hotel_data and len(hotel_data["offers"]) > 0:
            price_info = hotel_data["offers"][0].get("price", {})
            total_price = float(price_info.get("total", 0))
            currency = price_info.get("currency", "USD")
            daily_price = total_price  # This would need check-in/out dates to calculate properly
        
        return {
            "hotel_id": hotel_id,
            "name": name,
            "description": description,
            "address": address,
            "images": images,
            "rooms": rooms,
            "facilities": list(facilities),
            "rating": hotel_info.get("rating", None),
            "daily_price": daily_price or 100.0,
            "total_price": total_price or 100.0,
            "currency": currency
        }
    
    def get_city_code(self, destination: str) -> str:
        """
        Convert destination name to IATA city code
        This is a simplified version - in production, you'd use Amadeus Location API
        """
        # Simple mapping for common destinations
        city_mapping = {
            "new york": "NYC",
            "nyc": "NYC",
            "new york city": "NYC",
            "paris": "PAR",
            "london": "LON",
            "tokyo": "TYO",
            "tokyo": "TYO",
            "los angeles": "LAX",
            "lax": "LAX",
            "san francisco": "SFO",
            "sfo": "SFO",
            "chicago": "CHI",
            "miami": "MIA",
            "dubai": "DXB",
            "singapore": "SIN",
            "bangkok": "BKK",
            "sydney": "SYD",
            "rome": "ROM",
            "barcelona": "BCN",
            "amsterdam": "AMS",
            "berlin": "BER",
            "madrid": "MAD"
        }
        
        destination_lower = destination.lower().strip()
        return city_mapping.get(destination_lower, destination_lower.upper()[:3])

