import React, { useState, useEffect } from 'react';
import ChatWorkspace from './ChatWorkspace';
import useChatStream from '../hooks/useChatStream';
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

    // Real-time EventStream Consumer hook
    const { streamMessage, isStreaming, abortStream } = useChatStream();

    // Trigger Context load if the user types or deep-links directly into the workspace URL
    useEffect(() => {
        if (id && (!activeMachine || activeMachine.id.toString() !== id.toString())) {
            scanMachine(id);
        }
    }, [id, activeMachine, scanMachine]);

    // Welcome message initialization
    useEffect(() => {
        if (activeMachine && isMatchingId(activeMachine.id, id)) {
            setMessages([
                {
                    id: 'welcome',
                    sender: 'assistant',
                    text: `Ciao! Hai scansionato il QR di **${activeMachine.name}** (${activeMachine.modelType}).\nStato Corrente: **${activeMachine.status}**.\n\nCome posso esserti utile oggi per il troubleshooting?`,
                    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    status: 'sent',
                    citations: [],
                    metadata: {}
                }
            ]);
        }
    }, [activeMachine, id]);

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
            citations: []
        };

        setMessages((prev) => [...prev, aiPlaceholder]);

        // 3. Initiate Stream connection to POST /v1/chat/stream
        streamMessage({
            query: messageData.text,
            machineId: id,
            messageId: aiMessageId,
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
            onComplete: (finalMessage) => {
                // Swap the streaming bubble with the complete structured payload
                setMessages((prev) =>
                    prev.map((msg) =>
                        msg.id === aiMessageId ? finalMessage : msg
                    )
                );
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
        navigate('/');
    };

    return (
        <ChatWorkspace
            messages={messages}
            isLoading={isStreaming && messages[messages.length - 1]?.status === 'sending' && messages[messages.length - 1]?.text === ''}
            onSendMessage={handleSendMessage}
            onSuggestionClick={handleSuggestionClick}
            onBackClick={handleBackToFleet}
        />
    );
}