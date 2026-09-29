import { useCallback } from 'react';

/**
 * Custom React hook to communicate with AROL's FastAPI backend for chat history.
 *
 * Authentication is handled via the httpOnly session cookie (arol_session) that
 * the browser sends automatically when credentials: 'include' is set.
 * No Authorization header is needed.
 */
export default function useChatApi() {
    // Retrieve API URL from environment variables, fallback to local standard port 8000
    const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';

    /**
     * Fetches past conversation history for a given thread ID.
     *
     * @param {string} sessionId - The thread UUID to fetch history for.
     * @returns {Promise<Object|null>} The ConversationHistory object or null if failed.
     */
    const fetchChatHistory = useCallback(async (sessionId) => {
        if (!sessionId) return null;
        try {
            const response = await fetch(`${API_BASE_URL}/v1/conversations/${sessionId}/messages`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                },
                credentials: 'include', // sends arol_session cookie automatically
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