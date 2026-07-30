import { useState, useCallback, useRef } from 'react';

/**
 * Custom React hook to communicate with AROL's FastAPI backend orchestrator (POST /v1/chat).
 * Includes automatic contract mapping, request cancellation, and robust error management
 * optimized for rugged mobile connections.
 */
export default function useChatApi() {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    // Ref to hold the AbortController for request cancellation (e.g., if user navigates away)
    const abortControllerRef = useRef(null);

    // Retrieve API URL from environment variables, fallback to local standard port 8000
    const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';

    /**
     * Clears any active error state.
     */
    const clearError = useCallback(() => {
        setError(null);
    }, []);

    /**
     * Sends a message to the FastAPI orchestrator and returns a structured conversational bubble object.
     * 
     * @param {string} text - The troubleshooting question written or dictated by the operator.
     * @param {string} machineId - The active machine ID (defaults to 'generic' for Iteration 1 seed).
     * @returns {Promise<Object|null>} The mapped assistant message object, or null in case of error.
     */
    const sendMessage = useCallback(async (text, machineId = 'generic') => {
        // Cancel any pending request before starting a new one
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }

        // Create a new AbortController for this transaction
        const abortController = new AbortController();
        abortControllerRef.current = abortController;

        setIsLoading(true);
        setError(null);

        // Note: The Manuals Agent uses 'generic' as its seed machine_id in Iteration 1
        const targetMachineId = machineId || 'generic';

        try {
            const response = await fetch(`${API_BASE_URL}/v1/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                signal: abortController.signal,
                body: JSON.stringify({
                    message: text,
                    machine_id: targetMachineId,
                }),
            });

            // Handle HTTP level errors
            if (!response.ok) {
                let errorMessage = `Server responded with status ${response.status}`;
                try {
                    const errData = await response.json();
                    errorMessage = errData.detail || errorMessage;
                } catch {
                    // Fallback if response is not valid JSON
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();

            // Contract mapping: Translates FastAPI schema to ChatBubble.jsx expected props
            const mappedCitations = (data.citations || []).map((cit, index) => ({
                id: cit.id || `${cit.doc}-${cit.page}-${index}`,
                docName: cit.doc || 'Documento', // Maps backend "doc" to frontend "docName"
                page: cit.page || 1,
                snippet: cit.snippet || '' // Snippet metadata preserved for PDF viewer injection
            }));

            const assistantMessage = {
                id: `ai-${Date.now()}`,
                sender: 'assistant',
                text: data.answer || 'No response details received from AROL AI.',
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                status: 'sent',
                citations: mappedCitations,
                metadata: {
                    confidence: data.confidence || 1.0,
                    needsEscalation: data.needs_escalation || false
                }
            };

            return assistantMessage;

        } catch (err) {
            if (err.name === 'AbortError') {
                return null;
            }

            console.error('AROL Chat API Connection Error:', err);

            let technicianFriendlyError = 'Impossibile connettersi al server. Verifica la copertura Wi-Fi in fabbrica.';
            if (err.message) {
                technicianFriendlyError = `Errore di connessione: ${err.message}. Verifica la linea o contatta l'assistenza IT.`;
            }

            setError(technicianFriendlyError);
            throw new Error(technicianFriendlyError);

        } finally {
            if (abortControllerRef.current === abortController) {
                abortControllerRef.current = null;
            }
            setIsLoading(false);
        }
    }, [API_BASE_URL]);

    return {
        sendMessage,
        isLoading,
        error,
        clearError
    };
}