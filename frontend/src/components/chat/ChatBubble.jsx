import React from 'react';
import { FileText, AlertCircle, RotateCcw, Check } from 'lucide-react';
import { DEFAULT_CHAT_MESSAGE } from '../../models/ChatMessage';
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
    const { sender, text, timestamp, status, citations, metadata } = {
        ...DEFAULT_CHAT_MESSAGE,
        ...message,
    };

    // Check if the message is from the user
    const isUser = sender === 'user';

    // Parser for bullet lists for sequential maintenance instructions
    const renderContent = (contentString) => {
        if (!contentString) return null;
        const lines = contentString.split('\n');
        const jsxElements = [];
        let currentList = [];

        lines.forEach((line, index) => {
            const trimmed = line.trim();
            if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                currentList.push(
                    <li key={`li-${index}`} style={{ marginBottom: '4px' }}>
                        {trimmed.substring(2)}
                    </li>
                );
            } else {
                if (currentList.length > 0) {
                    jsxElements.push(
                        <ul key={`ul-${index}`} style={{ margin: '8px 0', paddingLeft: '20px', listStyleType: 'disc' }}>
                            {currentList}
                        </ul>
                    );
                    currentList = [];
                }
                if (trimmed) {
                    jsxElements.push(<p key={`p-${index}`} style={{ margin: '0 0 8px 0', lineHeight: '1.5' }}>{trimmed}</p>);
                }
            }
        });

        if (currentList.length > 0) {
            jsxElements.push(
                <ul key="ul-final" style={{ margin: '8px 0', paddingLeft: '20px', listStyleType: 'disc' }}>
                    {currentList}
                </ul>
            );
        }
        return jsxElements;
    };

    // Rendering the chat bubble
    return (
        <div className={`chat-row ${isUser ? 'user' : 'assistant'}`}>
            <div className="message-wrapper">
                <span className="message-sender">
                    {isUser ? 'Field Operator' : 'AROL AI Assistant'}
                </span>

                <div className="bubble">
                    <div className="bubble-text">{renderContent(text)}</div>

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

                    <div className="bubble-footer">
                        <span>{timestamp}</span>
                        {isUser && status === 'sent' && <Check size={12} style={{ color: 'rgba(255, 255, 255, 0.9)' }} />}
                        {!isUser && metadata.confidence && (
                            <span className="confidence-badge">
                                Verified ({Math.round(metadata.confidence * 100)}%)
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