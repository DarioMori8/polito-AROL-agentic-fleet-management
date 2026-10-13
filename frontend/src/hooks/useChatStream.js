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
    const USE_MOCK = import.meta.env?.VITE_USE_MOCK === 'true';

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
     * @param {string} messageId - The ID already assigned to the AI placeholder bubble.
     *   Reused in the finalMessage so the id stays consistent throughout the whole lifecycle
     *   (placeholder → streaming → complete). If omitted, a new id is generated as fallback.
     * @param {string} sessionId - Optional past session ID to resume from.
     * @param {Function} onToken - Callback triggered when a new text chunk is parsed: (tokenText) => {}
     * @param {Function} onThinking - Callback for reasoning chunks
     * @param {Function} onReset - Clear partial output when the backend recovers a failed generation.
     * @param {Function} onComplete - Callback triggered when the stream ends: (finalMessageObject) => {}
     * @param {Function} onError - Callback triggered on connection/parsing failure.
     * @param {Function} onSessionCreated - Callback triggered when the backend emits a session_id.
     */
    const streamMessage = useCallback(async ({
        query,
        machineId = 'generic',
        messageId,
        sessionId,
        onToken,
        onThinking,
        onReset,
        onComplete,
        onError,
        onSessionCreated
    }) => {
        // Abort any existing stream to prevent race conditions on fast-clicking operators
        abortStream();

        const abortController = new AbortController();
        abortControllerRef.current = abortController;

        setIsStreaming(true);
        setStreamError(null);

        // Streaming simulation for standalone tests
        if (USE_MOCK) {
            // 1. Simulate server reasoning delay
            await new Promise(resolve => setTimeout(resolve, 800));

            // 2. Mock response texts matching scanned machine queries
            const responseText = `Regarding your inquiry on machine ID ${machineId}, the anchoring torque specs must be tightly configured. As outlined in the technical manual, baseplate stabilization requires M16 steel rods tightened to exactly **120.0 Nm** on cured concrete [4]. Additionally, if you are experiencing excessive vibration on the capping head, please verify the roller bearings clearance which must stay between **0.05 mm and 0.12 mm** [1].`;

            // Split text into small word tokens to simulate active LLM streaming
            const tokens = responseText.split(/(\s+)/);
            let currentIndex = 0;

            const streamInterval = setInterval(() => {
                if (currentIndex < tokens.length) {
                    const nextChunk = tokens[currentIndex];
                    if (onToken) onToken(nextChunk);
                    currentIndex++;
                } else {
                    clearInterval(streamInterval);

                    // 3. Emit Mock Citations once streaming is finalized
                    const mockCitations = [
                        {
                            id: "cit-1",
                            doc: "Manuale_Euro_VP_Manutenzione.pdf",
                            page: 24,
                            snippet: "Routine inspection and lubrication of the idle rollers on the Euro VP capping head must be conducted every 500 operating hours. Vibration alarms can be prevented by maintaining certified baseplate anchoring."
                        },
                        {
                            id: "cit-2",
                            doc: "Specifiche_Ancoraggio_AROL.pdf",
                            page: 15,
                            snippet: "Heavy duty anchoring requires M16 threaded rods, class 8.8 steel, tightened with a torque wrench to 120.0 Nm (±5 Nm tolerance) inside cured concrete of min 25 MPa."
                        }
                    ];

                    const finalMessage = {
                        id: messageId || `ai-${Date.now()}`,
                        sender: 'assistant',
                        text: responseText,
                        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                        status: 'sent',
                        citations: mockCitations.map((cit, idx) => ({
                            id: `${cit.doc}-${cit.page}-${idx}`,
                            docName: cit.doc,
                            page: cit.page,
                            snippet: cit.snippet
                        })),
                        metadata: { confidence: 0.94, needsEscalation: false, sessionId: "mock-session-12345" }
                    };

                    setIsStreaming(false);
                    if (onComplete) onComplete(finalMessage);
                }
            }, 45); // Smooth streaming speed (~45ms per token block)

            // Store interval ref on AbortController to allow user to interrupt mock stream
            abortControllerRef.current = {
                abort: () => {
                    clearInterval(streamInterval);
                    setIsStreaming(false);
                }
            };
            return;
        }

        // Real backend streaming
        // The arol_session cookie is sent automatically by the browser (credentials: 'include').
        // No Authorization header needed.
        try {
            const response = await fetch(`${API_BASE_URL}/v1/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream',
                },
                credentials: 'include',
                signal: abortController.signal,
                body: JSON.stringify({
                    query: query,
                    machine_id: machineId,
                    thread_id: sessionId   // backend field name is thread_id
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
            let currentSessionId = sessionId;
            let confidence = null;
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

                    // Parse SSE fields: event and data.
                    // eventType starts as null — frames without an explicit 'event:' line
                    // fall through to the default case rather than being misrouted as 'message'.
                    // Multiple 'data:' lines in a single frame are concatenated per the SSE spec.
                    let eventType = null;
                    let dataPayload = '';

                    const lines = part.split('\n');
                    for (const line of lines) {
                        if (line.startsWith('event:')) {
                            eventType = line.slice('event:'.length).trim();
                        } else if (line.startsWith('data:')) {
                            // Concatenate multi-line data fields with a newline, as the SSE spec requires
                            const chunk = line.slice('data:'.length).trim();
                            dataPayload = dataPayload ? dataPayload + '\n' + chunk : chunk;
                        }
                    }

                    if (!dataPayload) continue;

                    let parsedData;
                    try {
                        parsedData = JSON.parse(dataPayload);
                    } catch (jsonErr) {
                        console.warn('Unable to parse SSE frame data payload:', dataPayload, jsonErr);
                        continue;
                    }

                    // Handle event types matching our FastAPI LangGraph orchestrator contract
                    switch (eventType) {
                        case 'start':
                            // Backend sends thread_id from the very first event
                            if (parsedData.thread_id) {
                                currentSessionId = parsedData.thread_id;
                                if (onSessionCreated) onSessionCreated(currentSessionId);
                            }
                            break;

                        case 'thinking':
                            // LLM internal reasoning chunks — forwarded to optional UI collapsible panel
                            if (onThinking && parsedData.text) {
                                onThinking(parsedData.text);
                            }
                            break;

                        case 'reset':
                            accumulatedText = '';
                            if (onReset) onReset();
                            break;

                        case 'token':
                            // Incrementally streaming single words or characters
                            const textChunk = parsedData.text || '';
                            if (textChunk) {
                                accumulatedText += textChunk;
                                if (onToken) onToken(textChunk);
                            }
                            break;

                        case 'status':
                            // Tool invocation announced by the backend (e.g. "Consulting manuals_agent...")
                            // Can be forwarded to a loading indicator if needed
                            break;

                        case 'sources':
                            if (Array.isArray(parsedData.sources)) {
                                citations = parsedData.sources
                                    .filter((source) => source.kind === 'manual')
                                    .map((cit, idx) => ({
                                        id: cit.id || `${cit.doc}-${cit.page}-${idx}`,
                                        docName: cit.doc || 'Documento',
                                        page: cit.page || 1,
                                        snippet: cit.snippet || ''
                                    }));
                            }
                            break;

                        case 'citations':
                            // parsedData is {type, citations: [...]} — NOT the array itself
                            if (Array.isArray(parsedData.citations)) {
                                citations = parsedData.citations.map((cit, idx) => ({
                                    id: cit.id || `${cit.doc}-${cit.page}-${idx}`,
                                    docName: cit.doc || 'Documento', // Maps "doc" from backend to "docName" in frontend
                                    page: cit.page || 1,
                                    snippet: cit.snippet || ''
                                }));
                            }
                            break;

                        case 'done':
                            // Final event — capture thread_id for the next turn
                            if (parsedData.thread_id) {
                                currentSessionId = parsedData.thread_id;
                                if (onSessionCreated) onSessionCreated(currentSessionId);
                            }
                            break;

                        case 'error':
                            if (!parsedData.recoverable) {
                                throw new Error(parsedData.message || 'An error occurred during LLM graph execution.');
                            }
                            // Recoverable tool errors are logged but don't abort the stream
                            console.warn('Recoverable agent error:', parsedData.message);
                            break;

                        default:
                            // Unknown event type — log and skip.
                            // Do NOT forward to onToken: an unrecognised 'thinking' frame
                            // would otherwise leak into the visible response text.
                            console.warn('useChatStream: unhandled SSE event type:', eventType, parsedData);
                            break;
                    }
                }
            }

            // Finalize the assembled stream message
            const finalMessage = {
                id: messageId || `ai-${Date.now()}`,
                sender: 'assistant',
                text: accumulatedText || 'Non è stata generata una risposta. Riprova la richiesta.',
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                status: 'sent',
                citations: citations,
                metadata: {
                    confidence: confidence,
                    needsEscalation: needsEscalation,
                    sessionId: currentSessionId
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
