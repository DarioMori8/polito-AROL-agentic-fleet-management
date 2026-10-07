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
     * Fetches the list of conversations for the current user, filtered by machine.
     *
     * Endpoint: GET /v1/conversations?machine_id={machineId}
     * Expected response: [ { thread_id, preview, created_at }, ... ]
     * The user is identified server-side from the arol_session cookie.
     *
     * @param {string} machineId - Machine ID to filter conversations by.
     * @returns {Promise<Array>} List of conversation metadata, or [] on failure.
     */
    const fetchConversations = useCallback(async (machineId) => {
        try {
            const params = machineId ? `?machine_id=${encodeURIComponent(machineId)}` : '';
            const response = await fetch(`${API_BASE_URL}/v1/conversations${params}`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' },
                credentials: 'include',
            });
            if (!response.ok) return [];
            return await response.json(); // [{ thread_id, preview, created_at }, ...]
        } catch (err) {
            console.error('AROL Chat API: fetchConversations error:', err);
            return [];
        }
    }, [API_BASE_URL]);

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
                headers: { 'Accept': 'application/json' },
                credentials: 'include',
            });
            if (!response.ok) return null;
            return await response.json();
        } catch (err) {
            console.error('AROL Chat API History Fetch Error:', err);
            return null;
        }
    }, [API_BASE_URL]);

    return { fetchConversations, fetchChatHistory };
}