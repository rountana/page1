import uuid
from typing import Dict, Optional, List
from datetime import date
from models.booking import BookingRequest, BookingResponse, BookingStatus, PaymentResponse


class BookingService:
    """Service for managing bookings with in-memory storage"""
    
    def __init__(self):
        # In-memory storage: booking_id -> booking_data
        self.bookings: Dict[str, Dict] = {}
        # Hotel name cache for bookings
        self.hotel_names: Dict[str, str] = {}
    
    def create_booking(self, booking_request: BookingRequest, hotel_name: str) -> BookingResponse:
        """Create a new booking"""
        booking_id = str(uuid.uuid4())
        
        # Calculate total price (simplified - would come from hotel details)
        nights = (booking_request.check_out - booking_request.check_in).days
        total_price = 150.0 * nights * booking_request.travelers  # Default price calculation
        
        booking_data = {
            "booking_id": booking_id,
            "hotel_id": booking_request.hotel_id,
            "hotel_name": hotel_name,
            "check_in": booking_request.check_in,
            "check_out": booking_request.check_out,
            "travelers": booking_request.travelers,
            "guest_info": booking_request.guest_info.dict(),
            "status": BookingStatus.PENDING,
            "total_price": total_price,
            "currency": "USD",
            "room_type": booking_request.room_type
        }
        
        self.bookings[booking_id] = booking_data
        self.hotel_names[booking_request.hotel_id] = hotel_name
        
        return BookingResponse(**booking_data)
    
    def get_booking(self, booking_id: str) -> Optional[BookingResponse]:
        """Get booking by ID"""
        booking_data = self.bookings.get(booking_id)
        if booking_data:
            return BookingResponse(**booking_data)
        return None
    
    def process_payment(self, booking_id: str) -> PaymentResponse:
        """Simulate payment processing"""
        booking_data = self.bookings.get(booking_id)
        
        if not booking_data:
            return PaymentResponse(
                success=False,
                message="Booking not found",
                booking_id=booking_id
            )
        
        if booking_data["status"] == BookingStatus.PAID:
            return PaymentResponse(
                success=True,
                message="Payment already processed",
                booking_id=booking_id,
                transaction_id=f"TXN-{booking_id[:8]}"
            )
        
        # Simulate payment success
        booking_data["status"] = BookingStatus.PAID
        transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        
        return PaymentResponse(
            success=True,
            message="Payment successful! Your booking is confirmed.",
            booking_id=booking_id,
            transaction_id=transaction_id
        )
    
    def get_all_bookings(self) -> List[BookingResponse]:
        """Get all bookings (for admin/debugging purposes)"""
        return [BookingResponse(**booking) for booking in self.bookings.values()]

