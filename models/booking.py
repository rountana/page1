from pydantic import BaseModel
from typing import Optional
from datetime import date
from enum import Enum


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PAID = "paid"
    CANCELLED = "cancelled"


class GuestInfo(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None


class BookingRequest(BaseModel):
    hotel_id: str
    check_in: date
    check_out: date
    travelers: int
    guest_info: GuestInfo
    room_type: Optional[str] = None


class BookingResponse(BaseModel):
    booking_id: str
    hotel_id: str
    hotel_name: str
    check_in: date
    check_out: date
    travelers: int
    guest_info: GuestInfo
    status: BookingStatus
    total_price: float
    currency: str = "USD"
    room_type: Optional[str] = None


class PaymentRequest(BaseModel):
    booking_id: str


class PaymentResponse(BaseModel):
    success: bool
    message: str
    booking_id: str
    transaction_id: Optional[str] = None

