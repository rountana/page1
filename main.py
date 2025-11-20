from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Optional
from datetime import date
import os

from models.hotel import HotelSearchRequest, HotelSearchResponse, HotelDetails
from models.booking import BookingRequest, BookingResponse, PaymentRequest, PaymentResponse
from services.amadeus_service import AmadeusService
from services.booking_service import BookingService
from services.google_places_service import GooglePlacesService

app = FastAPI(title="Travel Booking API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Initialize services
amadeus_service = AmadeusService()
booking_service = BookingService()
google_places_service = GooglePlacesService()


@app.get("/")
async def read_root():
    """Serve the main search page"""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Travel Booking API - Frontend not found"}


@app.get("/hotel-details.html")
async def hotel_details_page():
    """Serve the hotel details page"""
    details_path = os.path.join(static_dir, "hotel_details.html")
    if os.path.exists(details_path):
        return FileResponse(details_path)
    raise HTTPException(status_code=404, detail="Hotel details page not found")


@app.get("/booking-confirmation.html")
async def booking_confirmation_page():
    """Serve the booking confirmation page"""
    confirmation_path = os.path.join(static_dir, "booking_confirmation.html")
    if os.path.exists(confirmation_path):
        return FileResponse(confirmation_path)
    raise HTTPException(status_code=404, detail="Booking confirmation page not found")


@app.post("/api/hotels/search", response_model=HotelSearchResponse)
async def search_hotels(request: HotelSearchRequest):
    """Search for hotels based on destination, dates, and travelers"""
    try:
        # Convert destination to lower case
        request.destination = request.destination.lower()
        # Convert destination to city code
        city_code = amadeus_service.get_city_code(request.destination)
        
        # Search hotels via Amadeus API
        hotels_data = await amadeus_service.search_hotels(
            city_code=city_code,
            check_in=request.check_in,
            check_out=request.check_out,
            adults=request.travelers
        )

        import json
        print("================================================")
        print("hotels_data (first 3 items)")
        print("================================================")
        print(json.dumps(hotels_data[:3], indent=4))
        # Convert to response model
        from models.hotel import HotelSummary, HotelImage, HotelPrice
        
        hotel_summaries = []
        for hotel_data in hotels_data:
            images = [HotelImage(**img) for img in hotel_data.get("images", [])]
            price = HotelPrice(
                daily=hotel_data.get("daily_price"),
                total=hotel_data.get("total_price"),
                currency=hotel_data.get("currency", "USD")
            )
            
            hotel_summary = HotelSummary(
                hotel_id=hotel_data.get("hotel_id"),
                name=hotel_data.get("name"),
                images=images,
                price=price,
                address=hotel_data.get("address"),
                rating=hotel_data.get("rating"),
                latitude=hotel_data.get("latitude"),
                longitude=hotel_data.get("longitude")
            )
            hotel_summaries.append(hotel_summary)
        
        return HotelSearchResponse(
            hotels=hotel_summaries,
            total=len(hotel_summaries)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching hotels: {str(e)}")


@app.get("/api/hotels/{hotel_id}", response_model=HotelDetails)
async def get_hotel_details(
    hotel_id: str,
    check_in: Optional[date] = Query(None, description="Check-in date (YYYY-MM-DD)"),
    check_out: Optional[date] = Query(None, description="Check-out date (YYYY-MM-DD)"),
    adults: int = Query(1, description="Number of adults")
):
    """Get detailed information about a specific hotel"""
    try:
        hotel_data = await amadeus_service.get_hotel_details(
            hotel_id, 
            check_in=check_in, 
            check_out=check_out, 
            adults=adults
        )
        
        if not hotel_data:
            raise HTTPException(status_code=404, detail="Hotel not found")
        
        # Convert to response model
        from models.hotel import HotelImage, HotelPrice, RoomType, RoomFacility
        
        images = [HotelImage(**img) for img in hotel_data.get("images", [])]
        
        rooms = []
        for room_data in hotel_data.get("rooms", []):
            facilities = [RoomFacility(**fac) for fac in room_data.get("facilities", [])]
            room_price = HotelPrice(
                daily=None,
                total=room_data.get("price", {}).get("total"),
                currency=room_data.get("price", {}).get("currency", "USD")
            )
            room = RoomType(
                type=room_data.get("type"),
                description=room_data.get("description"),
                facilities=facilities,
                price=room_price,
                max_occupancy=room_data.get("max_occupancy")
            )
            rooms.append(room)
        
        price = HotelPrice(
            daily=hotel_data.get("daily_price"),
            total=hotel_data.get("total_price"),
            currency=hotel_data.get("currency", "USD")
        )
        
        return HotelDetails(
            hotel_id=hotel_data.get("hotel_id"),
            name=hotel_data.get("name"),
            description=hotel_data.get("description"),
            address=hotel_data.get("address"),
            images=images,
            rooms=rooms,
            facilities=hotel_data.get("facilities", []),
            rating=hotel_data.get("rating"),
            price=price
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting hotel details: {str(e)}")


@app.post("/api/hotels/google-places")
async def get_google_places_data(
    hotel_name: str = Body(...),
    address: str = Body(...),
    latitude: Optional[float] = Body(None),
    longitude: Optional[float] = Body(None)
):
    """
    Get Google Places reviews and images for a hotel
    
    Args:
        hotel_name: Hotel name from Amadeus
        address: Hotel address from Amadeus
        latitude: Latitude from Amadeus geoCode (optional)
        longitude: Longitude from Amadeus geoCode (optional)
    
    Returns:
        Dictionary with reviews, photo_references, and place_id
    """
    try:
        place_data = await google_places_service.get_hotel_reviews_and_images(
            hotel_name=hotel_name,
            address=address,
            latitude=latitude,
            longitude=longitude
        )
        
        if not place_data:
            return JSONResponse(
                status_code=404,
                content={"message": "Hotel not found in Google Places"}
            )
        
        # Convert photo references to URLs
        photos = []
        for photo_ref in place_data.get("photo_references", []):
            photo_url = await google_places_service.get_photo_url(
                photo_ref.get("photo_reference"),
                max_width=800,
                max_height=600,
                photo_name=photo_ref.get("name")  # Pass photo name for new API
            )
            if photo_url:
                photos.append({
                    "url": photo_url,
                    "width": photo_ref.get("widthPx") or photo_ref.get("width"),
                    "height": photo_ref.get("heightPx") or photo_ref.get("height"),
                    "attributions": photo_ref.get("authorAttributions") or photo_ref.get("html_attributions", [])
                })
        
        return {
            "place_id": place_data.get("place_id"),
            "reviews": place_data.get("reviews", []),
            "photos": photos,
            "google_rating": place_data.get("rating"),
            "google_ratings_total": place_data.get("user_ratings_total")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Google Places data: {str(e)}")


@app.post("/api/bookings", response_model=BookingResponse)
async def create_booking(booking_request: BookingRequest):
    """Create a new booking"""
    try:
        # Get hotel name from Amadeus (or use cached name)
        hotel_name = booking_service.hotel_names.get(booking_request.hotel_id)
        if not hotel_name:
            hotel_data = await amadeus_service.get_hotel_details(
                booking_request.hotel_id,
                check_in=booking_request.check_in,
                check_out=booking_request.check_out,
                adults=booking_request.travelers
            )
            hotel_name = hotel_data.get("name", "Unknown Hotel") if hotel_data else "Unknown Hotel"
        
        booking = booking_service.create_booking(booking_request, hotel_name)
        return booking
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating booking: {str(e)}")


@app.post("/api/bookings/{booking_id}/pay", response_model=PaymentResponse)
async def process_payment(booking_id: str, payment_request: PaymentRequest):
    """Simulate payment processing"""
    try:
        if payment_request.booking_id != booking_id:
            raise HTTPException(status_code=400, detail="Booking ID mismatch")
        
        result = booking_service.process_payment(booking_id)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing payment: {str(e)}")


@app.get("/api/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(booking_id: str):
    """Get booking details by ID"""
    booking = booking_service.get_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

