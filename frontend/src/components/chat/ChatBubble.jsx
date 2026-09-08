import React, { useState } from 'react';
import { FileText, AlertCircle, RotateCcw, Check, ChevronDown } from 'lucide-react';
import { DEFAULT_CHAT_MESSAGE } from '../../models/ChatMessage';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import '@/styles/ChatBubble.css';

/**
 * ChatBubble Component
 * @param {Object} message - The message to display
 * @param {Function} onCitationClick - Callback for when a citation is clicked
 * @param {Function} onRetry - Callback for when a message needs to be retried
 * @returns {JSX.Element}
 */
export default function ChatBubble({ message, onCitationClick, onRetry }) {
    // Structure of the message object
    const { sender, text, timestamp, status, citations, thinkingText } = {
        ...DEFAULT_CHAT_MESSAGE,
        ...message,
    };

    // Local state for the collapsible AI reasoning panel
    const [isThinkingOpen, setIsThinkingOpen] = useState(false);

    // Check if the message is from the user
    const isUser = sender === 'user';
    const displayText = !isUser && status === 'sending' && !text ? '▍' : text;

    // Rendering the chat bubble
    return (
        <div className={`chat-row ${isUser ? 'user' : 'assistant'}`}>
            <div className="message-wrapper">
                <span className="message-sender">
                    {isUser ? 'Field Operator' : 'AROL AI Assistant'}
                </span>

                <div className="bubble">
                    {/* AI Thinking Accordion — shown only for assistant messages with reasoning content */}
                    {!isUser && thinkingText && (
                        <div className="thinking-accordion">
                            <button
                                className="thinking-toggle"
                                onClick={() => setIsThinkingOpen((open) => !open)}
                                aria-expanded={isThinkingOpen}
                            >
                                <span className="thinking-toggle-icon">💭</span>
                                <span className="thinking-toggle-label">
                                    {isThinkingOpen ? 'Nascondi ragionamento' : 'Mostra ragionamento'}
                                </span>
                                <ChevronDown
                                    size={14}
                                    className={`thinking-chevron ${isThinkingOpen ? 'open' : ''}`}
                                />
                            </button>
                            <div className={`thinking-panel ${isThinkingOpen ? 'expanded' : ''}`}>
                                <p className="thinking-content">{thinkingText}</p>
                            </div>
                        </div>
                    )}

                    {/* Display the message text */}
                    <div className="bubble-text">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {displayText}
                        </ReactMarkdown>
                    </div>

                    {/* Interactive citations from Technical Manuals */}
                    {!isUser && citations && citations.length > 0 && (
                        <div className="citations-container">
                            {citations.map((cit, idx) => (
                                <button
                                    key={`cit-${idx}`}
                                    className="citation-badge"
                                    onClick={() => onCitationClick && onCitationClick(cit)}
                                >
                                    <FileText className="citation-icon" />
                                    <span>{cit.docName || 'Manual'} {cit.page ? `(p. ${cit.page})` : ''}</span>
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Display the message footer with timestamp and confidence badge */}
                    <div className="bubble-footer">
                        <span>{timestamp}</span>
                        {isUser && status === 'sent' && <Check size={12} style={{ color: 'rgba(255, 255, 255, 0.9)' }} />}
                        {!isUser && citations?.length > 0 && (
                            <span className="confidence-badge">
                                Fonti disponibili
                            </span>
                        )}
                    </div>
                </div>

                {/* Recovery block for network disconnections */}
                {isUser && status === 'error' && (
                    <div className="bubble-error-container">
                        <AlertCircle size={16} className="error-text" style={{ marginRight: '4px', flexShrink: 0 }} />
                        <span className="error-text">Message not sent. No signal.</span>
                        <button className="retry-button" onClick={() => onRetry && onRetry(message)}>
                            <RotateCcw size={12} style={{ marginRight: '4px' }} />
                            Retry
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}