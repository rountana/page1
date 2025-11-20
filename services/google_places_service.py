import os
import httpx
import asyncio
import argparse
import json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from services.cache_service import AmadeusCacheService

load_dotenv()


class GooglePlacesService:
    """Service for interacting with Google Places API (New) to get reviews and images"""
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_PLACES_API_KEY")
        self.base_url = "https://places.googleapis.com/v1"
        
        # Initialize cache service for Google Places API calls
        self.cache_service = AmadeusCacheService()
        
        if not self.api_key:
            print("Warning: GOOGLE_PLACES_API_KEY not set. Google Places features will be unavailable.")
    
    async def find_place_id(
        self, 
        hotel_name: str, 
        address: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> Optional[str]:
        """
        Find Google Place ID for a hotel using name, address, and geolocation
        Uses the new Places API (Text Search)
        
        Args:
            hotel_name: Hotel name from Amadeus
            address: Hotel address from Amadeus
            latitude: Latitude from Amadeus geoCode (optional)
            longitude: Longitude from Amadeus geoCode (optional)
            
        Returns:
            Google Place ID or None if not found
        """
        if not self.api_key:
            return None
        
        try:
            # Use Text Search API (New) with name and address
            endpoint = f"{self.base_url}/places:searchText"
            
            # Build text query
            query = f"{hotel_name} {address}"
            
            # Prepare request body
            request_body: Dict[str, Any] = {
                "textQuery": query,
                "maxResultCount": 1
            }
            
            # Add location bias if coordinates available
            if latitude and longitude:
                request_body["locationBias"] = {
                    "circle": {
                        "center": {
                            "latitude": latitude,
                            "longitude": longitude
                        },
                        "radius": 5000.0  # 5km radius in meters
                    }
                }
            
            # Add place type filter for lodging
            request_body["includedType"] = "lodging"
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(endpoint, json=request_body, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                if "places" in data and data["places"]:
                    # Find best match by comparing name similarity
                    best_match = self._find_best_match(data["places"], hotel_name, address)
                    if best_match:
                        place_id = best_match.get("id")
                        if place_id:
                            # Extract just the ID if it's a full resource name (places/ChIJ...)
                            if "/" in place_id:
                                place_id = place_id.split("/")[-1]
                            print(f"Found Place ID using text search: {place_id}")
                            return place_id
            
            print(f"Could not find Place ID for hotel: {hotel_name}")
            return None
            
        except httpx.HTTPStatusError as e:
            print(f"HTTP error finding Place ID: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            print(f"Error finding Place ID: {e}")
            return None
    
    def _find_best_match(
        self, 
        results: List[Dict[str, Any]], 
        hotel_name: str, 
        address: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find the best matching place from search results
        Handles new API response structure with displayName.text
        
        Args:
            results: List of place results from Google API (New)
            hotel_name: Original hotel name
            address: Original address
            
        Returns:
            Best matching place result or None
        """
        if not results:
            return None
        
        hotel_name_lower = hotel_name.lower()
        
        # Score each result based on name similarity
        scored_results = []
        for result in results:
            # New API uses displayName.text instead of name
            display_name = result.get("displayName", {})
            result_name = display_name.get("text", "").lower() if isinstance(display_name, dict) else ""
            
            score = 0
            
            # Exact name match gets highest score
            if result_name == hotel_name_lower:
                score = 100
            # Partial name match
            elif hotel_name_lower in result_name or result_name in hotel_name_lower:
                score = 80
            # Check if key words match
            else:
                hotel_words = set(hotel_name_lower.split())
                result_words = set(result_name.split())
                common_words = hotel_words.intersection(result_words)
                if common_words:
                    score = len(common_words) * 10
            
            scored_results.append((score, result))
        
        # Sort by score and return best match
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        # Only return if score is reasonable (at least 50)
        if scored_results and scored_results[0][0] >= 50:
            return scored_results[0][1]
        
        # Fallback to first result if no good match
        return results[0] if results else None
    
    async def get_place_details(
        self, 
        place_id: str,
        include_reviews: bool = True,
        include_photos: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get place details including reviews and photos from Google Places API (New)
        
        Args:
            place_id: Google Place ID
            include_reviews: Whether to include reviews
            include_photos: Whether to include photo references
            
        Returns:
            Dictionary with reviews, photos, and other details
        """
        if not self.api_key or not place_id:
            return None
        
        try:
            # Ensure place_id is just the ID, not the full resource name
            clean_place_id = place_id.split("/")[-1] if "/" in place_id else place_id
            endpoint = f"{self.base_url}/places/{clean_place_id}"
            
            # Build field mask for requested fields
            field_mask_parts = ["id", "displayName", "formattedAddress", "rating", "userRatingCount"]
            if include_reviews:
                field_mask_parts.append("reviews")
            if include_photos:
                field_mask_parts.append("photos")
            
            field_mask = ",".join(field_mask_parts)
            
            headers = {
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": field_mask
            }
            
            # For cache key, use endpoint and headers (since params are now in headers)
            cache_key_params = {"place_id": clean_place_id, "field_mask": field_mask}
            
            # Check cache first
            print(f"Checking cache for Google Places data (place_id: {clean_place_id})")
            cached_response = await self.cache_service.get(endpoint, cache_key_params)
            if cached_response:
                print(f"Google Places cache HIT - returning cached data for place_id: {clean_place_id}")
                return cached_response
            
            print(f"Google Places cache MISS - fetching from API for place_id: {clean_place_id}")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(endpoint, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                # Extract display name
                display_name = result.get("displayName", {})
                name = display_name.get("text", "") if isinstance(display_name, dict) else ""
                
                # Extract reviews (new API structure)
                reviews = []
                if include_reviews and "reviews" in result:
                    for review in result.get("reviews", [])[:5]:  # Limit to 5 reviews
                        author = review.get("authorAttribution", {})
                        author_name = author.get("displayName", "") if isinstance(author, dict) else ""
                        
                        # New API uses publishTime instead of time
                        publish_time = review.get("publishTime", "")
                        relative_time = review.get("relativePublishTimeDescription", "")
                        
                        reviews.append({
                            "author_name": author_name,
                            "rating": review.get("rating"),
                            "text": review.get("text", {}).get("text", "") if isinstance(review.get("text"), dict) else review.get("text", ""),
                            "time": publish_time,
                            "relative_time_description": relative_time
                        })
                
                # Extract photo references (new API structure)
                photo_references = []
                if include_photos and "photos" in result:
                    for photo in result.get("photos", [])[:10]:  # Limit to 10 photos
                        # New API uses name field like "places/{place_id}/photos/{photo_id}"
                        photo_name = photo.get("name", "")
                        photo_id = photo_name.split("/")[-1] if "/" in photo_name else photo_name
                        
                        photo_references.append({
                            "photo_reference": photo_id,  # Store photo ID for new API
                            "name": photo_name,  # Store full name for media endpoint
                            "widthPx": photo.get("widthPx"),
                            "heightPx": photo.get("heightPx"),
                            "authorAttributions": photo.get("authorAttributions", [])
                        })
                
                place_details = {
                    "place_id": clean_place_id,
                    "name": name,
                    "address": result.get("formattedAddress", ""),
                    "rating": result.get("rating"),
                    "user_ratings_total": result.get("userRatingCount"),
                    "reviews": reviews,
                    "photo_references": photo_references
                }
                
                # Cache the response
                print(f"Storing Google Places data in cache for place_id: {clean_place_id} (name: {place_details.get('name', 'unknown')})")
                await self.cache_service.set(endpoint, cache_key_params, place_details)
                print(f"Successfully cached Google Places data for place_id: {clean_place_id}")
                
                return place_details
                
        except httpx.HTTPStatusError as e:
            print(f"HTTP error getting place details: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            print(f"Error getting place details: {e}")
            return None
    
    async def get_photo_url(
        self, 
        photo_reference: str, 
        max_width: int = 800,
        max_height: int = 600,
        photo_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Get actual photo URL from photo reference using new Places API
        
        Args:
            photo_reference: Photo ID or name from place details
            max_width: Maximum width of photo
            max_height: Maximum height of photo
            photo_name: Full photo name (places/{place_id}/photos/{photo_id}) if available
            
        Returns:
            Photo URL or None
        """
        if not self.api_key:
            return None
        
        try:
            # New API uses: places/{place_id}/photos/{photo_id}/media
            # Prefer photo_name if available (it's the full path)
            if photo_name and photo_name.startswith("places/"):
                photo_path = photo_name
            elif "/" in photo_reference and photo_reference.startswith("places/"):
                # Assume it's already a full path
                photo_path = photo_reference
            else:
                # We need the full photo name path - if we only have photo_reference (ID),
                # we can't construct the URL without place_id
                print(f"Warning: Cannot construct photo URL without photo_name for reference: {photo_reference}")
                return None
            
            endpoint = f"{self.base_url}/{photo_path}/media"
            
            # Build query parameters
            params = {
                "maxWidthPx": max_width,
                "maxHeightPx": max_height,
                "key": self.api_key  # API key can be in query for media endpoint
            }
            
            # Construct the full URL
            # The media endpoint returns a redirect to the actual image
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            url = f"{endpoint}?{query_string}"
            return url
            
        except Exception as e:
            print(f"Error getting photo URL: {e}")
            return None
    
    async def get_hotel_reviews_and_images(
        self,
        hotel_name: str,
        address: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Complete workflow: Find place ID and get reviews/images
        
        Args:
            hotel_name: Hotel name from Amadeus
            address: Hotel address from Amadeus
            latitude: Latitude from Amadeus geoCode
            longitude: Longitude from Amadeus geoCode
            
        Returns:
            Dictionary with place_id, reviews, and photo_references, or None
        """
        # Step 1: Find Place ID
        place_id = await self.find_place_id(hotel_name, address, latitude, longitude)
        
        if not place_id:
            return None
        
        # Step 2: Get place details (reviews and photos)
        place_details = await self.get_place_details(place_id)
        
        return place_details


async def main():
    """CLI entry point for testing Google Places Service"""
    
    
    service = GooglePlacesService()
    
    if not service.api_key:
        print("Error: GOOGLE_PLACES_API_KEY environment variable is not set.")
        print("Please set it in your .env file or environment variables.")
        return
    
    name = "Hotel Kursaal"
    address = "Str. Stefan cel Mare 1, Sibiu, Romania"
    latitude = 45.801321
    longitude = 24.142531

    try:
            print(f"Searching for Place ID: {name} at {address}")
            place_id = await service.find_place_id(
                hotel_name=name,
                address=address,
                latitude=latitude,
                longitude=longitude
            )
            if place_id:
                print(f"\n✓ Found Place ID: {place_id}")
            else:
                print("\n✗ Could not find Place ID")
        
       
    
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
