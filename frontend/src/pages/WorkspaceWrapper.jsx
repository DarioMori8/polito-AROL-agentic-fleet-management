import React, { useState, useEffect, useCallback } from 'react';
import ChatWorkspace from './ChatWorkspace';
import useChatStream from '../hooks/useChatStream';
import useChatApi from '../hooks/useChatApi';
import { useMachine, isMatchingId } from '../context/MachineContext';
import { useNavigate, useParams } from 'react-router';

/**
 * WorkspaceWrapper Component
 * Handles conversational mock API states and feeds ChatWorkspace based on URL route ID
 */
export default function WorkspaceWrapper() {
    const { id } = useParams();
    const navigate = useNavigate();
    const { activeMachine, scanMachine } = useMachine();

    const [messages, setMessages] = useState([]);
    const [isAiLoading, setIsAiLoading] = useState(false);

    // Sidebar state & Sessions state
    const [isDrawerOpen, setIsDrawerOpen] = useState(false);
    const [sessionsList, setSessionsList] = useState([]);
    const [currentSessionId, setCurrentSessionId] = useState(null);

    // API hooks
    const { fetchChatHistory } = useChatApi();
    const { streamMessage, isStreaming, abortStream } = useChatStream();

    // Trigger Context load if the user types or deep-links directly into the workspace URL
    useEffect(() => {
        if (id && (!activeMachine || activeMachine.id.toString() !== id.toString())) {
            scanMachine(id);
        }
    }, [id, activeMachine, scanMachine]);

    // Helper to fetch and map history
    const loadSessionHistory = useCallback(async (sessionIdToLoad) => {
        const history = await fetchChatHistory(sessionIdToLoad);
        if (history && history.messages && history.messages.length > 0) {
            const historyMessages = history.messages.map((msg, idx) => ({
                id: `history-${idx}-${Date.now()}`,
                sender: msg.role === 'user' ? 'user' : 'assistant',
                text: msg.content,
                timestamp: '', 
                status: 'sent',
                citations: (msg.sources || []).map((cit, citIdx) => ({
                    id: cit.id || `${cit.doc}-${cit.page}-${citIdx}`,
                    docName: cit.doc || 'Documento',
                    page: cit.page || 1,
                    snippet: cit.snippet || ''
                })),
                metadata: {}
            }));
            setMessages(historyMessages);
            return true;
        }
        return false;
    }, [fetchChatHistory]);

    const getWelcomeMessage = useCallback(() => {
        return {
            id: 'welcome',
            sender: 'assistant',
            text: `Ciao! Hai scansionato il QR di **${activeMachine?.name || activeMachine?.serial_number || 'Macchinario'}** (${activeMachine?.model_id || 'Standard'}).\nStato Corrente: **${activeMachine?.status || 'Operativo'}**.\n\nCome posso esserti utile oggi per il troubleshooting?`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            status: 'sent',
            citations: [],
            metadata: {}
        };
    }, [activeMachine]);

    // Welcome message & History initialization (only when machine ID changes)
    useEffect(() => {
        let isMounted = true;

        const initializeChat = async () => {
            if (activeMachine && isMatchingId(activeMachine.id, id)) {
                // Load sessions list
                const sessionsKey = `arol_sessions_${id}`;
                const savedSessions = JSON.parse(localStorage.getItem(sessionsKey) || '[]');
                
                if (isMounted) {
                    setSessionsList(savedSessions);
                }

                const sessionToLoad = savedSessions.length > 0 ? savedSessions[0].sessionId : null;
                
                if (sessionToLoad) {
                    if (isMounted) setCurrentSessionId(sessionToLoad);
                    const success = await loadSessionHistory(sessionToLoad);
                    if (success && isMounted) return;
                }

                // Fallback: No history found or history fetch failed
                if (isMounted) {
                    setCurrentSessionId(null);
                    setMessages([getWelcomeMessage()]);
                }
            }
        };

        initializeChat();

        return () => {
            isMounted = false;
        };
    }, [activeMachine, id, loadSessionHistory, getWelcomeMessage]);

    // Clean-up connection on unmount
    useEffect(() => {
        return () => abortStream();
    }, [abortStream]);

    /**
     * Orchestrates the message sending flow utilizing Server-Sent Events (SSE).
     */
    const handleSendMessage = async (messageData) => {
        // 1. Append User Message
        const userMessageTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const newUserMessage = {
            id: `user-${Date.now()}`,
            sender: 'user',
            text: messageData.text,
            timestamp: userMessageTime,
            status: 'sent'
        };

        setMessages((prev) => [...prev, newUserMessage]);

        // 2. Prepare Temporary AI streaming placeholder
        const aiMessageId = `ai-stream-${Date.now()}`;
        const aiPlaceholder = {
            id: aiMessageId,
            sender: 'assistant',
            text: '',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            status: 'sending',
            citations: [],
            thinkingText: ''
        };

        setMessages((prev) => [...prev, aiPlaceholder]);

        // 3. Initiate Stream connection to POST /v1/chat/stream
        streamMessage({
            query: messageData.text,
            machineId: id,
            messageId: aiMessageId,
            sessionId: currentSessionId,
            onSessionCreated: (newSessionId) => {
                // If it's a new session, update our state and localStorage
                if (newSessionId !== currentSessionId) {
                    setCurrentSessionId(newSessionId);
                    setSessionsList(prev => {
                        // Check if it already exists
                        if (prev.find(s => s.sessionId === newSessionId)) return prev;
                        
                        const newSessionObj = {
                            sessionId: newSessionId,
                            preview: messageData.text.substring(0, 40) + (messageData.text.length > 40 ? '...' : ''),
                            timestamp: Date.now()
                        };
                        const updated = [newSessionObj, ...prev];
                        localStorage.setItem(`arol_sessions_${id}`, JSON.stringify(updated));
                        return updated;
                    });
                }
            },
            onToken: (chunk) => {
                // Progressively write the text character-by-character
                setMessages((prev) =>
                    prev.map((msg) =>
                        msg.id === aiMessageId
                            ? { ...msg, text: msg.text + chunk }
                            : msg
                    )
                );
            },
            onThinking: (chunk) => {
                // Accumulate LLM internal reasoning chunks into the bubble's thinking panel
                setMessages((prev) =>
                    prev.map((msg) =>
                        msg.id === aiMessageId
                            ? { ...msg, thinkingText: (msg.thinkingText || '') + chunk }
                            : msg
                    )
                );
            },
            onComplete: (finalMessage) => {
                // Preserve accumulated thinkingText when swapping to the final message
                setMessages((prev) => {
                    const streamingMsg = prev.find((msg) => msg.id === aiMessageId);
                    const thinkingText = streamingMsg?.thinkingText || '';
                    return prev.map((msg) =>
                        msg.id === aiMessageId
                            ? { ...finalMessage, thinkingText }
                            : msg
                    );
                });
            },
            onError: (errText) => {
                // Render error state on failure for retry triggers
                setMessages((prev) =>
                    prev.map((msg) =>
                        msg.id === aiMessageId
                            ? { ...msg, text: `⚠️ Impossibile generare la risposta: ${errText}`, status: 'error' }
                            : msg
                    )
                );
            }
        });
    };

    const handleSuggestionClick = (chipId, actionText) => {
        handleSendMessage({ text: actionText });
    };

    const handleBackToFleet = () => {
        abortStream();
        setMessages([]);
        setCurrentSessionId(null);
        navigate('/');
    };

    const handleNewChat = () => {
        abortStream();
        setCurrentSessionId(null);
        setMessages([getWelcomeMessage()]);
    };

    const handleSelectSession = async (sessionId) => {
        abortStream();
        setCurrentSessionId(sessionId);
        await loadSessionHistory(sessionId);
    };

    return (
        <ChatWorkspace
            messages={messages}
            isLoading={isStreaming && messages[messages.length - 1]?.status === 'sending' && messages[messages.length - 1]?.text === '' && !messages[messages.length - 1]?.thinkingText}
            onSendMessage={handleSendMessage}
            onSuggestionClick={handleSuggestionClick}
            onBackClick={handleBackToFleet}
            onMenuToggle={() => setIsDrawerOpen(true)}
            isDrawerOpen={isDrawerOpen}
            onCloseDrawer={() => setIsDrawerOpen(false)}
            sessionsList={sessionsList}
            currentSessionId={currentSessionId}
            onSelectSession={handleSelectSession}
            onNewChat={handleNewChat}
        />
    );
}