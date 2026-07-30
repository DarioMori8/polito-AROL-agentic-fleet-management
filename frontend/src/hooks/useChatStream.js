import { useState, useCallback, useRef } from 'react';

/**
 * useChatStream Hook (PWA-Optimized & Rugged-Ready)
 * 
 * Establishes a highly resilient connection to AROL's FastAPI real-time orchestrator 
 * streaming endpoint: POST /v1/chat/stream.
 * 
 * Since standard browser EventSource only supports GET requests, this hook implements
 * a custom Fetch ReadableStream reader to consume POST-based Server-Sent Events (SSE)
 * token-by-token.
 */
export default function useChatStream() {
    const [isStreaming, setIsStreaming] = useState(false);
    const [streamError, setStreamError] = useState(null);

    // Track the active network request for cancellation on network drop or tab switch
    const abortControllerRef = useRef(null);

    const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';

    const clearStreamError = useCallback(() => setStreamError(null), []);

    /**
     * Resets any active streaming network request safely.
     */
    const abortStream = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        setIsStreaming(false);
    }, []);

    /**
     * Initiates the SSE stream. 
     * Updates the UI progressively token-by-token via the onToken callback.
     * 
     * @param {string} query - The operator's question.
     * @param {string} machineId - Scanned machine identifier.
     * @param {Function} onToken - Callback triggered when a new text chunk is parsed: (tokenText) => {}
     * @param {Function} onComplete - Callback triggered when the stream ends: (finalMessageObject) => {}
     * @param {Function} onError - Callback triggered on connection/parsing failure.
     */
    const streamMessage = useCallback(async ({
        query,
        machineId = 'generic',
        onToken,
        onComplete,
        onError
    }) => {
        // Abort any existing stream to prevent race conditions on fast-clicking operators
        abortStream();

        const abortController = new AbortController();
        abortControllerRef.current = abortController;

        setIsStreaming(true);
        setStreamError(null);

        // PERSISTENCE: Check if there is an active session_id in sessionStorage for this machine
        const sessionKey = `arol_session_id_${machineId}`;
        const savedSessionId = sessionStorage.getItem(sessionKey) || null;

        try {
            const response = await fetch(`${API_BASE_URL}/v1/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream',
                },
                signal: abortController.signal,
                body: JSON.stringify({
                    query: query,
                    machine_id: machineId,
                    session_id: savedSessionId
                }),
            });

            if (!response.ok) {
                let errorDetails = `Status code: ${response.status}`;
                try {
                    const errJson = await response.json();
                    errorDetails = errJson.detail || errorDetails;
                } catch {
                    // Standard response text fallback
                }
                throw new Error(errorDetails);
            }

            if (!response.body) {
                throw new Error("Server response body is empty. Streaming not supported.");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');

            let buffer = '';
            let accumulatedText = '';
            let citations = [];
            let sessionId = savedSessionId;
            let confidence = 1.0;
            let needsEscalation = false;

            // Read stream chunks continuously
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                // Append decoded text to buffer
                buffer += decoder.decode(value, { stream: true });

                // SSE frames are separated by double newlines (\n\n)
                const parts = buffer.split('\n\n');

                // Keep the last incomplete part in the buffer
                buffer = parts.pop();

                for (const part of parts) {
                    if (!part.trim()) continue;

                    // Parse SSE fields: event and data
                    let eventType = 'message';
                    let dataPayload = '';

                    const lines = part.split('\n');
                    for (const line of lines) {
                        if (line.startsWith('event:')) {
                            eventType = line.replace('event:', '').trim();
                        } else if (line.startsWith('data:')) {
                            dataPayload = line.replace('data:', '').trim();
                        }
                    }

                    if (!dataPayload) continue;

                    try {
                        const parsedData = JSON.parse(dataPayload);

                        // Handle event types matching our FastAPI LangGraph orchestrator contract
                        switch (eventType) {
                            case 'token':
                                // Incrementally streaming single words or characters
                                const textChunk = parsedData.text || parsedData.token || '';
                                if (textChunk) {
                                    accumulatedText += textChunk;
                                    if (onToken) onToken(textChunk);
                                }
                                break;

                            case 'citations':
                                // Capture references to map to the ManualViewer.jsx format
                                if (Array.isArray(parsedData)) {
                                    citations = parsedData.map((cit, idx) => ({
                                        id: cit.id || `${cit.doc}-${cit.page}-${idx}`,
                                        docName: cit.doc || 'Documento', // Maps "doc" from backend contract to "docName" in frontend
                                        page: cit.page || 1,
                                        snippet: cit.snippet || ''
                                    }));
                                }
                                break;

                            case 'session':
                            case 'metadata':
                                // Echo conversation ID to enable session persistence on subsequent turns
                                if (parsedData.session_id) {
                                    sessionId = parsedData.session_id;
                                    sessionStorage.setItem(sessionKey, sessionId);
                                }
                                if (parsedData.confidence !== undefined) {
                                    confidence = parsedData.confidence;
                                }
                                if (parsedData.needs_escalation !== undefined) {
                                    needsEscalation = parsedData.needs_escalation;
                                }
                                break;

                            case 'error':
                                throw new Error(parsedData.message || 'An error occurred during LLM graph execution.');

                            default:
                                // Fallback parsing for unstructured data
                                if (parsedData.answer) {
                                    accumulatedText = parsedData.answer;
                                    if (onToken) onToken(parsedData.answer);
                                }
                                break;
                        }
                    } catch (jsonErr) {
                        // Logging parser faults on malformed SSE frames
                        console.warn('Unable to parse SSE frame data payload:', dataPayload, jsonErr);
                    }
                }
            }

            // Finalize the assembled stream message
            const finalMessage = {
                id: `ai-${Date.now()}`,
                sender: 'assistant',
                text: accumulatedText || 'Query processed successfully.',
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                status: 'sent',
                citations: citations,
                metadata: {
                    confidence: confidence,
                    needsEscalation: needsEscalation,
                    sessionId: sessionId
                }
            };

            setIsStreaming(false);
            if (onComplete) {
                onComplete(finalMessage);
            }

        } catch (err) {
            if (err.name === 'AbortError') {
                setIsStreaming(false);
                return; // Safe exit on user navigation abort
            }

            console.error('AROL SSE Streaming Error:', err);

            const friendlyError = err.message?.includes('Failed to fetch')
                ? 'Connessione instabile. Riconnessione Wi-Fi in corso...'
                : `Errore flusso dati: ${err.message}`;

            setStreamError(friendlyError);
            setIsStreaming(false);

            if (onError) {
                onError(friendlyError);
            }
        }
    }, [API_BASE_URL, abortStream]);

    return {
        streamMessage,
        abortStream,
        isStreaming,
        streamError,
        clearStreamError
    };
}