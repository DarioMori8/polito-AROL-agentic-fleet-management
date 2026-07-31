import React, { useRef, useEffect } from 'react';
import { ArrowLeft, Cpu, ShieldAlert, CheckCircle2, AlertTriangle, User } from 'lucide-react';
import ChatBubble from './ChatBubble';
import ChatInput from './ChatInput';
import SuggestionChips from './SuggestionChips';
import '../../styles/ChatWindow.css';

/**
 * ChatWindow Component
 * The main container for the chatbot conversation panel.
 * Handles the message feed, automated auto-scroll on new messages, 
 * machine state banner, and integration of input and quick action controls.
 */
export default function ChatWindow({
    messages = [],
    activeMachine = null,
    isLoading = false,
    onSendMessage,
    onSuggestionClick,
    onBackClick,
    onCitationClick,
    onRetryMessage
}) {
    const messagesEndRef = useRef(null);
    const scrollContainerRef = useRef(null);

    // Automated auto-scroll to the bottom of the feed when a new message or streaming token arrives
    const scrollToBottom = () => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isLoading]);

    // Helper function to render the correct machine status icon and badge style
    const renderStatusBadge = (status) => {
        const sanitizedStatus = status ? status.toLowerCase() : '';

        if (sanitizedStatus.includes('allarme') || sanitizedStatus.includes('errore')) {
            return (
                <span className="status-indicator badge-error">
                    <ShieldAlert size={14} className="status-icon" />
                    {status}
                </span>
            );
        }
        if (sanitizedStatus.includes('manutenzione')) {
            return (
                <span className="status-indicator badge-warning">
                    <AlertTriangle size={14} className="status-icon" />
                    {status}
                </span>
            );
        }
        return (
            <span className="status-indicator badge-success">
                <CheckCircle2 size={14} className="status-icon" />
                {status || 'Operativo'}
            </span>
        );
    };

    return (
        <div className="chat-window-layout">
            {/* 1. INDUSTRIAL HEADER - Back button, Machine info and operator silhouette */}
            <header className="chat-header">
                <button
                    className="header-back-btn"
                    onClick={onBackClick}
                    aria-label="Go back to fleet view"
                >
                    <ArrowLeft size={24} />
                </button>

                <div className="header-machine-info">
                    <div className="machine-title-row">
                        <Cpu size={18} className="machine-hardware-icon" />
                        <h1 className="machine-name">{activeMachine?.name || 'Macchinario AROL'}</h1>
                    </div>
                    <div className="machine-meta-row">
                        <span className="machine-id">ID: {activeMachine?.id || '---'}</span>
                        {activeMachine?.status && renderStatusBadge(activeMachine.status)}
                    </div>
                </div>

                <div className="header-operator-profile" title="Operator Profile">
                    <User size={20} />
                </div>
            </header>

            {/* 2. CONVERSATION FEED - Scrollable area for messages */}
            <main className="chat-messages-viewport" ref={scrollContainerRef}>
                <div className="messages-scroll-area">
                    {messages
                        .filter((msg) => !(msg.status === 'sending' && msg.text === ''))
                        .map((msg) => (
                        <ChatBubble
                            key={msg.id}
                            message={msg}
                            onCitationClick={onCitationClick}
                            onRetry={onRetryMessage}
                        />
                    ))}

                    {/* AI Thinking / Streaming Indicator */}
                    {isLoading && (
                        <div className="chat-row assistant">
                            <div className="message-wrapper">
                                <span className="message-sender">Assistente AROL AI</span>
                                <div className="bubble thinking-bubble">
                                    <div className="thinking-dots">
                                        <span className="dot"></span>
                                        <span className="dot"></span>
                                        <span className="dot"></span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Anchor element used to anchor the scroll-to-bottom calculation */}
                    <div ref={messagesEndRef} />
                </div>
            </main>

            {/* 3. INTERACTIVE FOOTER - Quick access Suggestion Chips and Input Bar */}
            <footer className="chat-footer-controls">
                {/* Render suggestion chips only if there are no pending loadings to avoid input conflicts */}
                {!isLoading && onSuggestionClick && (
                    <div className="chips-wrapper-scroll">
                        <SuggestionChips onSuggestionClick={onSuggestionClick} />
                    </div>
                )}

                <ChatInput
                    onSendMessage={onSendMessage}
                    disabled={isLoading}
                    placeholder={isLoading ? "Wait..." : "Type here..."}
                />
            </footer>
        </div>
    );
}