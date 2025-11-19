// API Base URL
const API_BASE = '/api';

// Get hotel ID from URL parameters
const urlParams = new URLSearchParams(window.location.search);
const hotelId = urlParams.get('hotel_id');

// Store hotel data and booking dates
let hotelData = null;
let searchParams = null;

// Load hotel details on page load
document.addEventListener('DOMContentLoaded', async function() {
    if (!hotelId) {
        showError('Hotel ID is missing');
        return;
    }
    
    // Try to get search params from sessionStorage
    const storedParams = sessionStorage.getItem('searchParams');
    if (storedParams) {
        searchParams = JSON.parse(storedParams);
        if (searchParams.checkIn) {
            document.getElementById('checkIn').value = searchParams.checkIn;
        }
        if (searchParams.checkOut) {
            document.getElementById('checkOut').value = searchParams.checkOut;
        }
        if (searchParams.travelers) {
            document.getElementById('travelers').value = searchParams.travelers;
        }
    }
    
    // Set minimum dates
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('checkIn').setAttribute('min', today);
    document.getElementById('checkOut').setAttribute('min', today);
    
    document.getElementById('checkIn').addEventListener('change', function() {
        const checkInDate = this.value;
        document.getElementById('checkOut').setAttribute('min', checkInDate);
    });
    
    await loadHotelDetails();
});

async function loadHotelDetails() {
    try {
        const response = await fetch(`${API_BASE}/hotels/${hotelId}`);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to load hotel details');
        }
        
        hotelData = await response.json();
        displayHotelDetails(hotelData);
        
    } catch (error) {
        showError(error.message);
    }
}

function displayHotelDetails(hotel) {
    // Hide loading, show details
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('hotelDetails').classList.remove('hidden');
    
    // Hotel name and address
    document.getElementById('hotelName').textContent = hotel.name;
    if (hotel.address) {
        document.getElementById('hotelAddress').textContent = hotel.address;
    }
    
    // Rating
    if (hotel.rating) {
        document.getElementById('hotelRating').innerHTML = `
            <div class="flex items-center">
                <span class="text-yellow-400 text-2xl">★</span>
                <span class="ml-2 text-gray-700 text-lg font-semibold">${hotel.rating.toFixed(1)}</span>
            </div>
        `;
    }
    
    // Description
    if (hotel.description) {
        document.getElementById('hotelDescription').textContent = hotel.description;
    }
    
    // Images
    const imagesContainer = document.getElementById('hotelImages');
    if (hotel.images && hotel.images.length > 0) {
        hotel.images.slice(0, 3).forEach(img => {
            const imgElement = document.createElement('img');
            imgElement.src = img.url || 'https://via.placeholder.com/400x250?text=No+Image';
            imgElement.alt = hotel.name;
            imgElement.className = 'w-full h-64 object-cover';
            imgElement.onerror = function() {
                this.src = 'https://via.placeholder.com/400x250?text=No+Image';
            };
            imagesContainer.appendChild(imgElement);
        });
    } else {
        const imgElement = document.createElement('img');
        imgElement.src = 'https://via.placeholder.com/400x250?text=No+Image';
        imgElement.alt = hotel.name;
        imgElement.className = 'w-full h-64 object-cover';
        imagesContainer.appendChild(imgElement);
    }
    
    // Prices
    const dailyPrice = hotel.price.daily ? `$${hotel.price.daily.toFixed(2)}` : 'N/A';
    const totalPrice = hotel.price.total ? `$${hotel.price.total.toFixed(2)}` : 'N/A';
    document.getElementById('dailyPrice').textContent = dailyPrice;
    document.getElementById('totalPrice').textContent = totalPrice;
    
    // Rooms
    const roomsList = document.getElementById('roomsList');
    const roomTypeSelect = document.getElementById('roomType');
    
    if (hotel.rooms && hotel.rooms.length > 0) {
        hotel.rooms.forEach(room => {
            // Add to rooms list display
            const roomCard = document.createElement('div');
            roomCard.className = 'border border-gray-200 rounded-lg p-4';
            
            const facilitiesHtml = room.facilities && room.facilities.length > 0
                ? `<div class="mt-2">
                     <p class="text-sm font-medium text-gray-700 mb-1">Facilities:</p>
                     <ul class="list-disc list-inside text-sm text-gray-600">
                       ${room.facilities.map(f => `<li>${f.name}</li>`).join('')}
                     </ul>
                   </div>`
                : '';
            
            const price = room.price.total ? `$${room.price.total.toFixed(2)}` : 'N/A';
            
            roomCard.innerHTML = `
                <h4 class="text-lg font-semibold text-gray-800">${room.type}</h4>
                ${room.description ? `<p class="text-gray-600 text-sm mt-1">${room.description}</p>` : ''}
                ${facilitiesHtml}
                <div class="mt-3 pt-3 border-t border-gray-200">
                    <p class="text-sm text-gray-600">Price: <span class="font-bold text-blue-600">${price}</span></p>
                    ${room.max_occupancy ? `<p class="text-sm text-gray-600">Max Occupancy: ${room.max_occupancy} guests</p>` : ''}
                </div>
            `;
            roomsList.appendChild(roomCard);
            
            // Add to room type select
            const option = document.createElement('option');
            option.value = room.type;
            option.textContent = `${room.type} - ${price}`;
            roomTypeSelect.appendChild(option);
        });
    } else {
        roomsList.innerHTML = '<p class="text-gray-600">No room information available</p>';
    }
    
    // Facilities
    if (hotel.facilities && hotel.facilities.length > 0) {
        document.getElementById('facilitiesSection').classList.remove('hidden');
        const facilitiesList = document.getElementById('facilitiesList');
        hotel.facilities.forEach(facility => {
            const facilityItem = document.createElement('div');
            facilityItem.className = 'flex items-center p-2 bg-gray-50 rounded';
            facilityItem.innerHTML = `<span class="text-gray-700">${facility}</span>`;
            facilitiesList.appendChild(facilityItem);
        });
    }
}

// Booking form handler
document.getElementById('bookingForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const checkIn = document.getElementById('checkIn').value;
    const checkOut = document.getElementById('checkOut').value;
    const travelers = parseInt(document.getElementById('travelers').value);
    const roomType = document.getElementById('roomType').value;
    const firstName = document.getElementById('firstName').value;
    const lastName = document.getElementById('lastName').value;
    const email = document.getElementById('email').value;
    const phone = document.getElementById('phone').value;
    
    // Validate dates
    if (new Date(checkOut) <= new Date(checkIn)) {
        alert('Check-out date must be after check-in date');
        return;
    }
    
    await createBooking({
        hotel_id: hotelId,
        check_in: checkIn,
        check_out: checkOut,
        travelers,
        room_type: roomType || null,
        guest_info: {
            first_name: firstName,
            last_name: lastName,
            email,
            phone: phone || null
        }
    });
});

async function createBooking(bookingData) {
    const bookBtn = document.getElementById('bookBtn');
    bookBtn.disabled = true;
    bookBtn.textContent = 'Processing...';
    
    try {
        const response = await fetch(`${API_BASE}/bookings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(bookingData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create booking');
        }
        
        const booking = await response.json();
        // Redirect to confirmation page
        window.location.href = `/booking-confirmation.html?booking_id=${booking.booking_id}`;
        
    } catch (error) {
        alert('Error creating booking: ' + error.message);
        bookBtn.disabled = false;
        bookBtn.textContent = 'Book Now';
    }
}

function showError(message) {
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('errorMessage').textContent = message;
    document.getElementById('error').classList.remove('hidden');
}

