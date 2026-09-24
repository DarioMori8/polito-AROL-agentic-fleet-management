import { useCallback } from 'react';

const SESSION_KEY = 'arol_auth_session';

/**
 * Custom React hook to communicate with AROL's FastAPI backend for chat history.
 * Reads the JWT token from sessionStorage and attaches it as Authorization header.
 */
export default function useChatApi() {
    // Retrieve API URL from environment variables, fallback to local standard port 8000
    const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';

    /**
     * Fetches past conversation history for a given session ID.
     * 
     * @param {string} sessionId - The session ID to fetch history for.
     * @returns {Promise<Object|null>} The ConversationHistory object or null if failed.
     */
    const fetchChatHistory = useCallback(async (sessionId) => {
        if (!sessionId) return null;
        try {
            // Read JWT token from session (if authenticated)
            let authHeader = {};
            try {
                const session = JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
                if (session?.token) authHeader = { 'Authorization': `Bearer ${session.token}` };
            } catch { /* session parse failure is non-fatal */ }

            const response = await fetch(`${API_BASE_URL}/v1/conversations/${sessionId}/messages`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    ...authHeader
                }
            });
            if (!response.ok) {
                return null;
            }
            const data = await response.json();
            return data;
        } catch (err) {
            console.error('AROL Chat API History Fetch Error:', err);
            return null;
        }
    }, [API_BASE_URL]);

    return {
        fetchChatHistory
    };
}