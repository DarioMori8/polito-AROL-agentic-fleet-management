import React, { useState, useRef, useEffect } from 'react';
import { Send, Mic, Paperclip, X } from 'lucide-react';
import Button from '../ui/Button';
import '../../styles/ChatInput.css';

/**
 * ChatInput component optimized for industrial environments (Rugged UI).
 * Supports standard text input, voice dictation (Speech-to-Text), and attachment uploads.
 */
export default function ChatInput({
    onSendMessage,
    onAttachmentSelect,
    disabled = false,
    placeholder = "Type your message..."
}) {
    const [text, setText] = useState('');
    const [isListening, setIsListening] = useState(false);
    const [attachment, setAttachment] = useState(null);

    const textareaRef = useRef(null);
    const fileInputRef = useRef(null);
    const recognitionRef = useRef(null);

    // Initialize Web Speech API for hands-free troubleshooting in factory environments
    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            const recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = 'it-IT'; // Default language set to Italian for Italian plant operators

            recognition.onstart = () => setIsListening(true);
            recognition.onend = () => setIsListening(false);
            recognition.onerror = (event) => {
                console.error("Speech recognition error:", event.error);
                setIsListening(false);
            };
            recognition.onresult = (event) => {
                const speechToText = event.results[0][0].transcript || '';
                setText((prev) => prev ? `${prev} ${speechToText}` : speechToText);
            };

            recognitionRef.current = recognition;
        }
    }, []);

    // Dynamically auto-expand the textarea height (capped by CSS max-height to protect mobile viewport)
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    }, [text]);

    const handleSend = (e) => {
        if (e) e.preventDefault();
        if ((!(text || '').trim() && !attachment) || disabled) return;

        if (onSendMessage) {
            onSendMessage({
                text: (text || '').trim(),
                attachment: attachment
            });
        }

        // Reset local inputs after dispatching message
        setText('');
        setAttachment(null);
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
        }
    };

    const handleKeyDown = (e) => {
        // Send message on Enter key, allow shift+Enter for newlines
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const toggleListening = () => {
        if (!recognitionRef.current) {
            alert("Speech recognition is not supported in this browser. Please use Chrome or Safari on your rugged device.");
            return;
        }
        if (isListening) {
            recognitionRef.current.stop();
        } else {
            recognitionRef.current.start();
        }
    };

    const handleFileChange = (e) => {
        const file = e.target.files?.[0];
        if (file) {
            setAttachment(file);
            if (onAttachmentSelect) {
                onAttachmentSelect(file);
            }
        }
    };

    const triggerFileInput = () => {
        if (fileInputRef.current) {
            fileInputRef.current.click();
        }
    };

    const removeAttachment = () => {
        setAttachment(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    return (
        <form className="chat-input-form" onSubmit={handleSend}>
            {/* Dynamic Attachment Preview Bar */}
            {attachment && (
                <div className="attachment-preview">
                    <Paperclip size={14} className="preview-icon" />
                    <span className="preview-name">{attachment.name}</span>
                    <Button
                        variant="outline"
                        className="remove-attachment-btn"
                        onClick={removeAttachment}
                        type="button"
                        aria-label="Remove attachment"
                    >
                        <X size={14} />
                    </Button>
                </div>
            )}

            <div className="chat-input-container">
                {/* Speech-to-Text Button (Min 48x48px Touch Target) */}
                <Button
                    variant="outline"
                    className={`input-action-btn speech-btn ${isListening ? 'listening' : ''}`}
                    onClick={toggleListening}
                    disabled={disabled}
                    type="button"
                    title="Voice Dictation"
                    aria-label="Voice Dictation"
                >
                    <Mic size={20} />
                </Button>

                {/* Hidden native input for mobile file-picker or camera capture */}
                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    style={{ display: 'none' }}
                    accept="image/*,application/pdf"
                />

                {/* Attachment Button (Min 48x48px Touch Target) */}
                <Button
                    variant="outline"
                    className="input-action-btn attachment-btn"
                    onClick={triggerFileInput}
                    disabled={disabled}
                    type="button"
                    title="Attach Image/Document"
                    aria-label="Attach Image or Document"
                >
                    <Paperclip size={20} />
                </Button>

                {/* Dynamic growing Textarea */}
                <textarea
                    ref={textareaRef}
                    rows={1}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    disabled={disabled}
                    className="chat-textarea"
                    style={{ resize: 'none' }}
                />

                {/* Send Button (Min 48x48px Touch Target) */}
                <Button
                    variant="primary"
                    className="input-action-btn send-btn"
                    disabled={disabled || (!(text || '').trim() && !attachment)}
                    type="submit"
                    title="Send Message"
                    aria-label="Send Message"
                >
                    <Send size={20} />
                </Button>
            </div>
        </form>
    );
}