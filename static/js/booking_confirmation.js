// API Base URL
const API_BASE = '/api';

// Get booking ID from URL parameters
const urlParams = new URLSearchParams(window.location.search);
const bookingId = urlParams.get('booking_id');

let bookingData = null;

// Load booking details on page load
document.addEventListener('DOMContentLoaded', async function() {
    if (!bookingId) {
        showError('Booking ID is missing');
        return;
    }
    
    await loadBookingDetails();
});

async function loadBookingDetails() {
    try {
        const response = await fetch(`${API_BASE}/bookings/${bookingId}`);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to load booking details');
        }
        
        bookingData = await response.json();
        displayBookingDetails(bookingData);
        
    } catch (error) {
        showError(error.message);
    }
}

function displayBookingDetails(booking) {
    // Hide loading, show details
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('bookingDetails').classList.remove('hidden');
    
    // Booking ID
    document.getElementById('bookingId').textContent = booking.booking_id;
    
    // Hotel information
    document.getElementById('hotelName').textContent = booking.hotel_name;
    if (booking.hotel_address) {
        document.getElementById('hotelAddress').textContent = booking.hotel_address;
    }
    
    // Booking details
    document.getElementById('checkIn').textContent = formatDate(booking.check_in);
    document.getElementById('checkOut').textContent = formatDate(booking.check_out);
    document.getElementById('travelers').textContent = booking.travelers;
    
    if (booking.room_type) {
        document.getElementById('roomTypeInfo').classList.remove('hidden');
        document.getElementById('roomType').textContent = booking.room_type;
    }
    
    // Price
    const totalPrice = `$${booking.total_price.toFixed(2)} ${booking.currency}`;
    document.getElementById('totalPrice').textContent = totalPrice;
    
    // Guest information
    document.getElementById('guestName').textContent = `${booking.guest_info.first_name} ${booking.guest_info.last_name}`;
    document.getElementById('guestEmail').textContent = booking.guest_info.email;
    
    if (booking.guest_info.phone) {
        document.getElementById('guestPhoneContainer').classList.remove('hidden');
        document.getElementById('guestPhone').textContent = booking.guest_info.phone;
    }
    
    // Status
    const statusElement = document.getElementById('bookingStatus');
    statusElement.textContent = booking.status.toUpperCase();
    
    if (booking.status === 'paid') {
        statusElement.className = 'px-4 py-2 rounded-full text-sm font-semibold bg-green-100 text-green-800';
        document.getElementById('paymentSection').classList.add('hidden');
        showPaymentSuccess(booking);
    } else if (booking.status === 'confirmed') {
        statusElement.className = 'px-4 py-2 rounded-full text-sm font-semibold bg-blue-100 text-blue-800';
    } else {
        statusElement.className = 'px-4 py-2 rounded-full text-sm font-semibold bg-yellow-100 text-yellow-800';
    }
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    });
}

async function processPayment() {
    if (!bookingId) {
        alert('Booking ID is missing');
        return;
    }
    
    const payBtn = document.getElementById('payBtn');
    payBtn.disabled = true;
    payBtn.textContent = 'Processing Payment...';
    
    try {
        const response = await fetch(`${API_BASE}/bookings/${bookingId}/pay`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                booking_id: bookingId
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Payment failed');
        }
        
        const paymentResult = await response.json();
        
        if (paymentResult.success) {
            showPaymentSuccess(paymentResult);
            document.getElementById('paymentSection').classList.add('hidden');
            // Update booking status
            bookingData.status = 'paid';
            const statusElement = document.getElementById('bookingStatus');
            statusElement.textContent = 'PAID';
            statusElement.className = 'px-4 py-2 rounded-full text-sm font-semibold bg-green-100 text-green-800';
        } else {
            throw new Error(paymentResult.message || 'Payment failed');
        }
        
    } catch (error) {
        alert('Error processing payment: ' + error.message);
        payBtn.disabled = false;
        payBtn.textContent = 'Pay Now';
    }
}

function showPaymentSuccess(paymentResult) {
    document.getElementById('paymentSuccess').classList.remove('hidden');
    document.getElementById('successMessage').textContent = paymentResult.message || 'Your booking has been confirmed!';
    
    if (paymentResult.transaction_id) {
        document.getElementById('transactionId').textContent = `Transaction ID: ${paymentResult.transaction_id}`;
    }
}

function showError(message) {
    document.getElementById('loading').classList.add('hidden');
    document.getElementById('errorMessage').textContent = message;
    document.getElementById('error').classList.remove('hidden');
}

// Make processPayment available globally
window.processPayment = processPayment;

