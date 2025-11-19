# Travel Booking App

A travel booking web application built with FastAPI backend and HTML/Tailwind CSS/JavaScript frontend, integrated with Amadeus Self Service API for hotel search and booking.

## Features

1. **Hotel Search**: Search for hotels based on date, destination, and number of travelers
2. **Hotel Details**: View detailed hotel information including rooms and facilities
3. **Booking**: Book rooms and simulate payment (no actual payment processing)

## Setup

### Prerequisites

- Python 3.9+
- uv package manager
- Amadeus API credentials

### Installation

1. Install dependencies using uv:
```bash
uv pip install -r requirements.txt
```

Or create a virtual environment and install:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your Amadeus API credentials
```

3. Run the application:
```bash
uvicorn main:app --reload
```

The application will be available at `http://localhost:8000`

## Project Structure

```
page1/
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── services/
│   ├── __init__.py
│   ├── amadeus_service.py # Amadeus API integration
│   └── booking_service.py # Booking management
├── models/
│   ├── __init__.py
│   ├── hotel.py          # Hotel data models
│   └── booking.py        # Booking data models
└── static/
    ├── index.html        # Main search page
    ├── hotel_details.html # Hotel details page
    ├── booking_confirmation.html # Booking confirmation
    ├── css/
    │   └── style.css     # Custom styles (if needed)
    └── js/
        └── app.js        # Frontend JavaScript
```

## API Endpoints

- `GET /` - Home/search page
- `POST /api/hotels/search` - Search hotels
- `GET /api/hotels/{hotel_id}` - Get hotel details
- `POST /api/bookings` - Create booking
- `POST /api/bookings/{booking_id}/pay` - Simulate payment

## Amadeus API

This application uses the Amadeus Self Service API for hotel data. You'll need to:
1. Sign up at https://developers.amadeus.com
2. Create an app to get Client ID and Client Secret
3. Add credentials to your `.env` file

## License

MIT

