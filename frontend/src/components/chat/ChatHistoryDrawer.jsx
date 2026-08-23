import React from 'react';
import { Plus, MessageSquare, X, Clock } from 'lucide-react';
import '../../styles/ChatHistoryDrawer.css';

/**
 * ChatHistoryDrawer
 * A slide-out panel that displays past conversation sessions for the active machine.
 */
export default function ChatHistoryDrawer({
    isOpen,
    onClose,
    sessionsList = [],
    currentSessionId,
    onSelectSession,
    onNewChat
}) {
    return (
        <>
            {/* Backdrop for closing the drawer on click outside */}
            <div 
                className={`drawer-backdrop ${isOpen ? 'open' : ''}`} 
                onClick={onClose}
                aria-hidden="true"
            />
            
            <aside className={`chat-history-drawer ${isOpen ? 'open' : ''}`}>
                <div className="drawer-header">
                    <h2>Cronologia Chat</h2>
                    <button className="close-drawer-btn" onClick={onClose} aria-label="Chiudi cronologia">
                        <X size={24} />
                    </button>
                </div>

                <div className="drawer-actions">
                    <button className="new-chat-btn" onClick={() => {
                        onNewChat();
                        onClose();
                    }}>
                        <Plus size={20} />
                        Nuova Conversazione
                    </button>
                </div>

                <div className="drawer-sessions-list">
                    {sessionsList.length === 0 ? (
                        <div className="no-sessions-msg">
                            <p>Nessuna conversazione passata per questo macchinario.</p>
                        </div>
                    ) : (
                        sessionsList.map(session => (
                            <button
                                key={session.sessionId}
                                className={`session-item ${currentSessionId === session.sessionId ? 'active' : ''}`}
                                onClick={() => {
                                    onSelectSession(session.sessionId);
                                    onClose();
                                }}
                            >
                                <MessageSquare size={18} className="session-icon" />
                                <div className="session-details">
                                    <span className="session-preview">
                                        {session.preview || 'Nuova conversazione'}
                                    </span>
                                    <span className="session-time">
                                        <Clock size={12} />
                                        {new Date(session.timestamp).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                </div>
                            </button>
                        ))
                    )}
                </div>
            </aside>
        </>
    );
}
