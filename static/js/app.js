// API Base URL
const API_BASE = '/api';

// Set minimum date to today
document.addEventListener('DOMContentLoaded', function() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('checkIn').setAttribute('min', today);
    document.getElementById('checkOut').setAttribute('min', today);
    
    // Set check-out minimum to check-in date
    document.getElementById('checkIn').addEventListener('change', function() {
        const checkInDate = this.value;
        document.getElementById('checkOut').setAttribute('min', checkInDate);
    });
});

// Search form handler
document.getElementById('searchForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const destination = document.getElementById('destination').value;
    const checkIn = document.getElementById('checkIn').value;
    const checkOut = document.getElementById('checkOut').value;
    const travelers = parseInt(document.getElementById('travelers').value);
    
    // Validate dates
    if (new Date(checkOut) <= new Date(checkIn)) {
        showError('Check-out date must be after check-in date');
        return;
    }
    
    await searchHotels(destination, checkIn, checkOut, travelers);
});

async function searchHotels(destination, checkIn, checkOut, travelers) {
    // Hide previous results and errors
    hideAll();
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE}/hotels/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                destination,
                check_in: checkIn,
                check_out: checkOut,
                travelers
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to search hotels');
        }
        
        const data = await response.json();
        // displayHotels(data.hotels);
        
        // Write hotels data to JSON file for troubleshooting
        downloadHotelsJSON(data.hotels);
        
        
    } catch (error) {
        showError(error.message);
    } finally {
        hideLoading();
    }
}

function displayHotels(hotels) {
    const hotelsList = document.getElementById('hotelsList');
    hotelsList.innerHTML = '';
    
    if (hotels.length === 0) {
        document.getElementById('noResults').classList.remove('hidden');
        return;
    }
    
    document.getElementById('results').classList.remove('hidden');
    
    hotels.forEach(hotel => {
        const hotelCard = createHotelCard(hotel);
        hotelsList.appendChild(hotelCard);
    });
}

function createHotelCard(hotel) {
    const card = document.createElement('div');
    card.className = 'hotel-card bg-white rounded-lg shadow-md overflow-hidden cursor-pointer';
    
    // Hotel image
    const imageUrl = hotel.images && hotel.images.length > 0 
        ? hotel.images[0].url 
        : 'https://via.placeholder.com/400x250?text=No+Image';
    
    const imageHtml = `
        <img src="${imageUrl}" alt="${hotel.name}" class="w-full h-48 object-cover" 
             onerror="this.src='https://via.placeholder.com/400x250?text=No+Image'">
    `;
    
    // Price formatting
    const dailyPrice = hotel.price.daily ? `$${hotel.price.daily.toFixed(2)}` : 'N/A';
    const totalPrice = hotel.price.total ? `$${hotel.price.total.toFixed(2)}` : 'N/A';
    
    // Rating stars
    const ratingHtml = hotel.rating 
        ? `<div class="flex items-center mt-2">
             <span class="text-yellow-400">★</span>
             <span class="ml-1 text-gray-600">${hotel.rating.toFixed(1)}</span>
           </div>`
        : '';
    
    card.innerHTML = `
        ${imageHtml}
        <div class="p-4">
            <h3 class="text-xl font-semibold text-gray-800 mb-2">${hotel.name}</h3>
            ${hotel.address ? `<p class="text-gray-600 text-sm mb-2">${hotel.address}</p>` : ''}
            ${ratingHtml}
            <div class="mt-4 pt-4 border-t border-gray-200">
                <div class="flex justify-between items-center">
                    <div>
                        <p class="text-sm text-gray-600">Daily Rate</p>
                        <p class="text-lg font-bold text-blue-600">${dailyPrice}</p>
                    </div>
                    <div class="text-right">
                        <p class="text-sm text-gray-600">Total Price</p>
                        <p class="text-lg font-bold text-blue-600">${totalPrice}</p>
                    </div>
                </div>
            </div>
            <button 
                onclick="viewHotelDetails('${hotel.hotel_id}')"
                class="w-full mt-4 px-4 py-2 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors"
            >
                View Details
            </button>
        </div>
    `;
    
    return card;
}

function viewHotelDetails(hotelId) {
    // Store search parameters for use on details page
    const searchParams = {
        checkIn: document.getElementById('checkIn').value,
        checkOut: document.getElementById('checkOut').value,
        travelers: document.getElementById('travelers').value
    };
    sessionStorage.setItem('searchParams', JSON.stringify(searchParams));
    window.location.href = `/hotel-details.html?hotel_id=${hotelId}`;
}

function showLoading() {
    document.getElementById('loading').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

function showError(message) {
    document.getElementById('errorMessage').textContent = message;
    document.getElementById('error').classList.remove('hidden');
}

function hideAll() {
    document.getElementById('results').classList.add('hidden');
    document.getElementById('noResults').classList.add('hidden');
    document.getElementById('error').classList.add('hidden');
}

function downloadHotelsJSON(hotels) {
    // Create a JSON string with pretty formatting
    const jsonString = JSON.stringify(hotels, null, 2);
    
    // Create a Blob with the JSON data
    const blob = new Blob([jsonString], { type: 'application/json' });
    
    // Create a download link
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    
    // Generate filename with timestamp
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    link.download = `hotels-data-${timestamp}.json`;
    
    // Trigger download
    document.body.appendChild(link);
    link.click();
    
    // Clean up
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    
    console.log(`Downloaded hotels data: ${hotels.length} hotels`);
}

// Make viewHotelDetails available globally
window.viewHotelDetails = viewHotelDetails;

