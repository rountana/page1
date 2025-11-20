// API Base URL
const API_BASE = '/api';

// Storage key for consolidated Google Places data
const GOOGLE_PLACES_STORAGE_KEY = 'googlePlacesData';

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
        
        data.hotels.forEach(hotel => {
            loadGooglePlacesForHotel(hotel);
        });

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
        
        // Asynchronously fetch Google Places data to update hotel card
        loadGooglePlacesForHotel(hotel);
    });
}

function createHotelCard(hotel) {
    const card = document.createElement('div');
    card.className = 'hotel-card bg-white rounded-lg shadow-md overflow-hidden cursor-pointer';
    card.setAttribute('data-hotel-id', hotel.hotel_id);
    
    // Hotel image - use placeholder initially, will be updated by Google Places if available
    const imageUrl = hotel.images && hotel.images.length > 0 
        ? hotel.images[0].url 
        : 'https://via.placeholder.com/400x250?text=No+Image';
    
    const imageHtml = `
        <img src="${imageUrl}" alt="${hotel.name}" class="w-full h-48 object-cover hotel-card-image" 
             data-hotel-id="${hotel.hotel_id}"
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

/**
 * Download hotels data as JSON file
 * @param {Array} hotels - Array of hotel objects to download
 */
function downloadHotelsJSON(hotels) {
    try {
        // Validate input
        if (!hotels || !Array.isArray(hotels) || hotels.length === 0) {
            console.log('No hotels data to download');
            return;
        }
        
        // Create data structure with metadata
        const data = {
            total_hotels: hotels.length,
            generated_at: new Date().toISOString(),
            hotels: hotels
        };
        
        // Generate filename with timestamp
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
        const filename = `hotels-data-${timestamp}.json`;
        
        // Write to JSON file using shared helper
        writeJSONFile(data, filename);
        
        console.log(`Downloaded hotels data: ${hotels.length} hotels`);
        
    } catch (error) {
        console.error('Error downloading hotels data:', error);
    }
}

/**
 * Asynchronously load Google Places data for a hotel and update the hotel card image
 * @param {Object} hotel - Hotel object with name, address, and optional latitude/longitude
 */
async function loadGooglePlacesForHotel(hotel) {
    try {
        // Check if we have the required data
        if (!hotel.name || !hotel.address) {
            console.log(`Insufficient data for Google Places lookup: ${hotel.name || 'Unknown'}`);
            return;
        }
        
        const requestBody = {
            hotel_name: hotel.name,
            address: hotel.address,
            latitude: hotel.latitude || null,
            longitude: hotel.longitude || null
        };
        
        const response = await fetch(`${API_BASE}/hotels/google-places`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            // Silently fail - Google Places is optional, placeholder image will remain
            console.log(`Google Places data not available for hotel: ${hotel.name}`);
            return;
        }
        
        const googleData = await response.json();
        
        // Store Google Places data for this hotel
        storeGooglePlacesData(hotel.hotel_id, hotel.name, googleData);
        
        // Update hotel card image if photos are available
        if (googleData.photos && googleData.photos.length > 0) {
            updateHotelCardImage(hotel.hotel_id, googleData.photos[0].url);
        } else {
            // No image found, ensure placeholder is shown
            console.log(`No Google Places images found for hotel: ${hotel.name}`);
        }
        
    } catch (error) {
        console.error(`Error loading Google Places data for hotel ${hotel.name}:`, error);
        // Silently fail - Google Places is optional
    }
}

/**
 * Update the image of a hotel card when Google Places data is received
 * @param {string} hotelId - Hotel ID to identify the card
 * @param {string} imageUrl - URL of the image to display
 */
function updateHotelCardImage(hotelId, imageUrl) {
    // Find the hotel card image element
    const imageElement = document.querySelector(`img.hotel-card-image[data-hotel-id="${hotelId}"]`);
    
    if (imageElement && imageUrl) {
        // Update the image source
        imageElement.src = imageUrl;
        
        // Handle image load errors - fallback to placeholder
        imageElement.onerror = function() {
            this.src = 'https://via.placeholder.com/400x250?text=No+Image';
        };
        
        console.log(`Updated image for hotel card: ${hotelId}`);
    }
}

/**
 * Store Google Places data in sessionStorage for consolidated retrieval
 * @param {string} hotelId - Hotel ID
 * @param {string} hotelName - Hotel name
 * @param {Object} googleData - Google Places data
 */
function storeGooglePlacesData(hotelId, hotelName, googleData) {
    try {
        // Get existing consolidated data from sessionStorage
        const existingData = sessionStorage.getItem(GOOGLE_PLACES_STORAGE_KEY);
        let consolidatedData = existingData ? JSON.parse(existingData) : {};
        
        // Add this hotel's data
        consolidatedData[hotelId] = {
            hotel_id: hotelId,
            hotel_name: hotelName,
            google_places_data: googleData,
            timestamp: new Date().toISOString()
        };
        
        // Save back to sessionStorage
        sessionStorage.setItem(GOOGLE_PLACES_STORAGE_KEY, JSON.stringify(consolidatedData));
        
        console.log(`Stored Google Places data for hotel: ${hotelName} (${hotelId})`);
        console.log(`Total hotels with Google Places data: ${Object.keys(consolidatedData).length}`);
        
    } catch (error) {
        console.error('Error storing Google Places data:', error);
    }
}

/**
 * Download consolidated Google Places data as JSON file
 */
function downloadConsolidatedGooglePlacesJSON() {
    try {
        // Get all consolidated data from sessionStorage
        const existingData = sessionStorage.getItem(GOOGLE_PLACES_STORAGE_KEY);
        
        if (!existingData) {
            console.log('No Google Places data to download');
            return;
        }
        
        const consolidatedData = JSON.parse(existingData);
        
        // Convert object to array for easier consumption
        const dataArray = Object.values(consolidatedData);
        
        // Create final consolidated structure
        const finalData = {
            total_hotels: dataArray.length,
            generated_at: new Date().toISOString(),
            hotels: dataArray
        };
        
        // Write to JSON file
        writeJSONFile(finalData, `google-places-consolidated-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5)}.json`);
        
        console.log(`Downloaded consolidated Google Places data for ${dataArray.length} hotels`);
        
    } catch (error) {
        console.error('Error downloading consolidated Google Places data:', error);
    }
}

/**
 * Helper function to write JSON data to a downloadable file
 * @param {Object} data - Data to write
 * @param {string} filename - Filename for the download
 */
function writeJSONFile(data, filename) {
    try {
        // Create a JSON string with pretty formatting
        const jsonString = JSON.stringify(data, null, 2);
        
        // Create a Blob with the JSON data and proper MIME type
        const blob = new Blob([jsonString], { 
            type: 'application/json;charset=utf-8' 
        });
        
        // Create a download link
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename.endsWith('.json') ? filename : `${filename}.json`;
        link.style.display = 'none';
        
        // Trigger download
        document.body.appendChild(link);
        link.click();
        
        // Clean up after a short delay
        setTimeout(() => {
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        }, 100);
        
    } catch (error) {
        console.error('Error writing JSON file:', error);
        throw error;
    }
}

// Make functions available globally
window.viewHotelDetails = viewHotelDetails;
window.downloadConsolidatedGooglePlacesJSON = downloadConsolidatedGooglePlacesJSON;

