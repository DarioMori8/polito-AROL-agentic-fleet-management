import React, { useState } from 'react';
import ChatWindow from '../components/chat/ChatWindow';
import '../styles/index.css';
import '../styles/ChatWindow.css';
import '../styles/ChatBubble.css';
import '../styles/ChatInput.css';
import '../styles/SuggestionChips.css';
import '../styles/Button.css';

// --- CSF Meta (required by Storybook) ---
export default {
    title: 'UI/ChatWindow',
    component: ChatWindow,
};

// --- Interactive Demo Story (with simulated AI response) ---

/**
 * Wrapper that owns the state so that the story is fully interactive:
 * sending messages, loading indicator, simulated AI responses.
 */
function ChatWindowDemo() {
    const [messages, setMessages] = useState([
        {
            id: 'greetings',
            sender: 'assistant',
            text: "Ciao! Hai scansionato il QR della Macchina Capper #12.\nCome posso aiutarti oggi? Scegli un'opzione o scrivi.",
            timestamp: '15:30',
            status: 'sent'
        }
    ]);
    const [isLoading, setIsLoading] = useState(false);

    const activeMachine = {
        id: '001',
        name: 'AROL Capper #12',
        status: 'In Allarme'
    };

    const handleSendMessage = (messageData) => {
        const newUserMessage = {
            id: Date.now().toString(),
            sender: 'user',
            text: messageData.text,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            status: 'sent'
        };

        setMessages((prev) => [...prev, newUserMessage]);
        setIsLoading(true);

        // Simulate Orchestrator AI response after 1.5s
        setTimeout(() => {
            const systemResponse = {
                id: (Date.now() + 1).toString(),
                sender: 'assistant',
                text: `Ho rilevato la tua richiesta riguardo a: "${messageData.text}". Sto interrogando il Manuals Agent per estrarre le istruzioni di manutenzione.`,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                citations: [
                    { docName: 'Manuale_Capper_12.pdf', page: 24 }
                ],
                metadata: { confidence: 0.89 }
            };
            setMessages((prev) => [...prev, systemResponse]);
            setIsLoading(false);
        }, 1500);
    };

    const handleSuggestionClick = (actionId) => {
        console.log("Quick action selected:", actionId);
        if (actionId === 'troubleshoot') {
            handleSendMessage({ text: "Guida alla Risoluzione Guasti" });
        }
    };

    return (
        <div style={{ height: '100vh', width: '100%' }}>
            <ChatWindow
                messages={messages}
                activeMachine={activeMachine}
                isLoading={isLoading}
                onSendMessage={handleSendMessage}
                onSuggestionClick={handleSuggestionClick}
                onBackClick={() => console.log("Back to fleet view")}
                onCitationClick={(cit) => console.log("Opening PDF at page:", cit.page)}
            />
        </div>
    );
}

export const InteractiveDemo = () => <ChatWindowDemo />;