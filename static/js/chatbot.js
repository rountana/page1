/**
 * Chatbot module using Google Generative AI SDK
 * Handles initialization, context loading, and chat interactions
 */

class ChatBot {
    constructor() {
        this.chatHistory = [];
        this.systemInstruction = null;
        this.apiKey = null;
        this.initialized = false;
    }

    /**
     * Load API key from config file
     */
    async loadConfig() {
        try {
            const response = await fetch('/static/js/config.json');
            if (response.ok) {
                const config = await response.json();
                this.apiKey = config.GEMINI_API_KEY;
                return true;
            } else {
                console.error('Failed to load config.json');
                return false;
            }
        } catch (error) {
            console.error('Error loading config:', error);
            return false;
        }
    }

    /**
     * Load hotel context from data file
     */
    async loadHotelContext() {
        try {
            const response = await fetch('/static/data/data.json');
            if (response.ok) {
                const data = await response.json();
                const contextStr = JSON.stringify(data, null, 2);
                
                this.systemInstruction = `You are a helpful chat bot with memory. You remember details from the conversation.

Here is some context about hotels:
${contextStr}

Use this context to answer questions. If the answer is not explicitly in the file (e.g., proximity to landmarks like parks), use your general knowledge based on the address or coordinates provided in the file.

IMPORTANT: When you determine that the response must contain specific hotel/s. You MUST respond with a JSON object in the following format do not include any text:
{
  "hotel_ids": ["hotelId1", "hotelId2", ...],
  "reason_for_hotels_list": "Brief explanation of why these hotels were selected (e.g., 'These hotels are within 0.5 miles of Central Park' or 'These hotels are near subway stations')"
}

examples of such situations are when 
a. match hotels to a user's criteria (e.g., are near a park, close to subway, etc.), 
b. the user asks for a list of hotels (such as show me the hotels we were talking about earlier),

Remember: The JSON you provide will be rendered by the UI in a hotel card. So the user may ask to show you a list of hotels.

Do not provide hotel names in your response. Only provide the hotel_ids array.

only provide text response if there are no hotels to in the response`;
                
                return true;
            } else {
                console.warn('Could not load hotel context data');
                this.systemInstruction = 'You are a helpful chat bot with memory. You remember details from the conversation.';
                return false;
            }
        } catch (error) {
            console.error('Error loading hotel context:', error);
            this.systemInstruction = 'You are a helpful chat bot with memory. You remember details from the conversation.';
            return false;
        }
    }

    /**
     * Initialize the Gemini model
     */
    async initialize() {
        if (this.initialized) {
            return true;
        }

        // Load API key
        const configLoaded = await this.loadConfig();
        if (!configLoaded || !this.apiKey) {
            console.error('GEMINI_API_KEY not found in config.json');
            return false;
        }

        try {
            // Load hotel context first
            await this.loadHotelContext();

            // No need to initialize a model object - we'll use direct API calls
            this.initialized = true;
            console.log('ChatBot initialized successfully');
            return true;
        } catch (error) {
            console.error('Error initializing chatbot:', error);
            return false;
        }
    }

    /**
     * Send a chat message and get response using direct API calls
     * @param {string} message - User message
     * @returns {Promise<Object>} - Bot response object with {text, hotelData} where hotelData is null if no hotels
     */
    async sendMessage(message) {
        if (!this.initialized) {
            const initialized = await this.initialize();
            if (!initialized) {
                throw new Error('ChatBot not initialized. Please check your API key configuration.');
            }
        }

        if (!message || !message.trim()) {
            throw new Error('Message cannot be empty');
        }

        try {
            // Build contents array with history and current message
            const contents = [];
            
            // Add conversation history
            this.chatHistory.forEach(msg => {
                contents.push({
                    role: msg.role === 'user' ? 'user' : 'model',
                    parts: [{ text: msg.text }]
                });
            });
            
            // Add current message
            contents.push({
                role: 'user',
                parts: [{ text: message }]
            });

            // Build request payload
            const requestBody = {
                contents: contents
            };
            
            // Add system instruction if available (should be sent with every request for context)
            if (this.systemInstruction) {
                requestBody.systemInstruction = {
                    parts: [{ text: this.systemInstruction }]
                };
            }

            // Call Gemini API directly
            const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${this.apiKey}`;
            
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error?.message || `API error: ${response.status}`);
            }

            const data = await response.json();
            
            if (!data.candidates || !data.candidates[0] || !data.candidates[0].content) {
                throw new Error('Invalid response format from API');
            }

            const responseText = data.candidates[0].content.parts[0].text;

            // Try to parse as JSON to check if it contains hotel data
            let hotelData = null;
            let displayText = responseText;
            
            try {
                // Try to extract JSON from the response (might be wrapped in markdown code blocks)
                let jsonStr = responseText.trim();
                
                // Look for JSON code blocks anywhere in the string (not just at the start)
                // Match ```json ... ``` or ``` ... ```
                const jsonBlockRegex = /```(?:json)?\s*(\{[\s\S]*?\})\s*```/;
                const match = jsonStr.match(jsonBlockRegex);
                
                if (match && match[1]) {
                    // Found a JSON code block, extract the JSON content
                    jsonStr = match[1].trim();
                }
                
                const parsed = JSON.parse(jsonStr);
                
                // Check if it has the expected structure
                if (parsed.hotel_ids && Array.isArray(parsed.hotel_ids) && parsed.hotel_ids.length > 0) {
                    hotelData = {
                        hotel_ids: parsed.hotel_ids,
                        reason_for_hotels_list: parsed.reason_for_hotels_list || 'Hotels matching your criteria'
                    };
                    // Don't display the JSON text if we have hotel data
                    displayText = null;
                }
            } catch (e) {
                // Not JSON or doesn't match expected structure, treat as normal text response
                hotelData = null;
            }

            // Update chat history (store as simple objects)
            this.chatHistory.push({ role: 'user', text: message });
            this.chatHistory.push({ role: 'model', text: responseText });

            return {
                text: displayText,
                hotelData: hotelData
            };
        } catch (error) {
            console.error('Error sending message:', error);
            throw new Error(`Failed to get response: ${error.message}`);
        }
    }

    /**
     * Clear chat history
     */
    clearHistory() {
        this.chatHistory = [];
    }

    /**
     * Get initialization status
     */
    isInitialized() {
        return this.initialized;
    }
}

// Create singleton instance
const chatbot = new ChatBot();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = chatbot;
}

