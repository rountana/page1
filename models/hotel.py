from pydantic import BaseModel
from typing import Optional, List
from datetime import date


class HotelSearchRequest(BaseModel):
    destination: str
    check_in: date
    check_out: date
    travelers: int


class HotelImage(BaseModel):
    url: Optional[str] = None
    category: Optional[str] = None


class HotelPrice(BaseModel):
    daily: Optional[float] = None
    total: Optional[float] = None
    currency: Optional[str] = "USD"


class HotelSummary(BaseModel):
    hotel_id: str
    name: str
    images: List[HotelImage] = []
    price: HotelPrice
    address: Optional[str] = None
    rating: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class HotelSearchResponse(BaseModel):
    hotels: List[HotelSummary]
    total: int


class RoomFacility(BaseModel):
    name: str
    description: Optional[str] = None


class RoomType(BaseModel):
    type: str
    description: Optional[str] = None
    facilities: List[RoomFacility] = []
    price: HotelPrice
    max_occupancy: Optional[int] = None


class HotelDetails(BaseModel):
    hotel_id: str
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    images: List[HotelImage] = []
    rooms: List[RoomType] = []
    facilities: List[str] = []
    rating: Optional[float] = None
    price: HotelPrice

