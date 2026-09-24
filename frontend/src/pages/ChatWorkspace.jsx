import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { MessageSquare, BookOpen, QrCode } from 'lucide-react';
import { useMachine } from '../context/MachineContext';
import ChatWindow from '../components/chat/ChatWindow';
import ManualViewer from '../components/manuals/ManualViewer';
import ChatHistoryDrawer from '../components/chat/ChatHistoryDrawer';
import '../styles/ChatWorkspace.css';

/**
 * ChatWorkspace Component (Page-level Container)
 * Orchestrates the multi-view layout for mobile-first industrial operators.
 * Handles bottom tab navigation, tablet split-screen, and inter-component communication
 * (e.g., clicking a citation in Chat redirects to the Manuals tab on the correct page).
 */
export default function ChatWorkspace({
    messages = [],
    isLoading = false,
    onSendMessage,
    onBackClick,
    onSuggestionClick,
    onMenuToggle,
    isDrawerOpen,
    onCloseDrawer,
    sessionsList,
    currentSessionId,
    onSelectSession,
    onNewChat,
    loginGate = null   // Optional: render instead of chat when user is not authenticated
}) {
    const navigate = useNavigate()

    const { activeMachine, isScanned, clearMachine } = useMachine();

    // Mobile Tab State: 'chat' | 'manuals'
    const [activeTab, setActiveTab] = useState('chat');

    // Selected citation state passed to the ManualViewer
    const [selectedCitation, setSelectedCitation] = useState(null);

    // Tablet/Desktop Split-Screen state: true = split, false = tabbed
    const [isTabletLayout, setIsTabletLayout] = useState(() => typeof window !== 'undefined' && window.innerWidth >= 768);

    // Track window resizing to dynamically toggle split-screen rugged views
    useEffect(() => {
        const handleResize = () => {
            setIsTabletLayout(window.innerWidth >= 768);
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    // Safe fallback if user accesses workspace without a scanned machine
    if (!isScanned || !activeMachine) {
        return (
            <div className="workspace-empty-state">
                <div className="empty-card">
                    <h2>Nessun Macchinario Attivo</h2>
                    <p>Scansiona un QR code o seleziona un dispositivo dalla flotta per accedere al workspace.</p>
                    <button className="btn-rugged primary" onClick={onBackClick}>
                        Torna alla Flotta
                    </button>
                </div>
            </div>
        );
    }

    /**
     * Intercepts citation clicks in the chat feed.
     * Switches view to the 'manuals' section and triggers page navigation.
     */
    const handleCitationClick = (citation) => {
        setSelectedCitation(citation);
        setActiveTab('manuals');
    };

    const handleNewScan = () => {
        navigate('/scanner');
        clearMachine();
    };

    return (
        <div className={`workspace-container ${isTabletLayout ? 'tablet-split' : 'mobile-single'}`}>
            <ChatHistoryDrawer
                isOpen={isDrawerOpen}
                onClose={onCloseDrawer}
                sessionsList={sessionsList}
                currentSessionId={currentSessionId}
                onSelectSession={onSelectSession}
                onNewChat={onNewChat}
            />

            {/* ==========================================
                LAYOUT 1: TABLET SPLIT SCREEN (Multi-Column)
                ========================================== */}
            {isTabletLayout ? (
                <div className="split-layout-wrapper">
                    {/* Left Column: Chat or Login Gate */}
                    <aside className="split-column split-left">
                        {loginGate ? (
                            <div className="chat-login-gate-wrapper">{loginGate}</div>
                        ) : (
                            <ChatWindow
                                messages={messages}
                                activeMachine={activeMachine}
                                isLoading={isLoading}
                                onSendMessage={onSendMessage}
                                onSuggestionClick={onSuggestionClick}
                                onBackClick={onBackClick}
                                onCitationClick={handleCitationClick}
                                onMenuToggle={onMenuToggle}
                            />
                        )}
                    </aside>

                    {/* Right Column: Contextual Pane (Manual PDF) */}
                    <main className="split-column split-right">
                        <div className="split-right-header">
                            <button
                                className={`pane-tab-btn ${activeTab === 'manuals' ? 'active' : ''}`}
                                onClick={() => setActiveTab('manuals')}
                            >
                                <BookOpen size={16} />
                                Manuale Tecnico & PDF
                            </button>
                        </div>

                        {/* Reset padding to 0 when manuals are active to prevent double scrollbars on rugged screens */}
                        <div
                            className="pane-content-viewport"
                            style={{ padding: activeTab === 'manuals' ? 0 : '20px' }}
                        >
                            {/* Real interactive ManualViewer */}
                            <ManualViewer
                                selectedCitation={selectedCitation}
                                defaultDoc="Manuale_Euro_VP_Manutenzione.pdf"
                            />
                        </div>
                    </main>
                </div>
            ) : (
                /* ==========================================
                   LAYOUT 2: MOBILE SINGLE COLUMN (Tabbed View)
                   ========================================== */
                <div className="mobile-layout-wrapper">

                    {/* Main Display Area */}
                    <main className="mobile-view-viewport">
                        {activeTab === 'chat' && (
                            loginGate ? (
                                <div className="chat-login-gate-wrapper">{loginGate}</div>
                            ) : (
                                <ChatWindow
                                    messages={messages}
                                    activeMachine={activeMachine}
                                    isLoading={isLoading}
                                    onSendMessage={onSendMessage}
                                    onSuggestionClick={onSuggestionClick}
                                    onBackClick={onBackClick}
                                    onCitationClick={handleCitationClick}
                                    onMenuToggle={onMenuToggle}
                                />
                            )
                        )}

                        {activeTab === 'manuals' && (
                            <div className="mobile-pane-wrapper">
                                <header className="mobile-pane-header">
                                    <h2>Technical Documentation</h2>
                                    <span className="machine-tag">{activeMachine.name}</span>
                                </header>
                                <div className="pane-content-viewport" style={{ padding: 0 }}>
                                    <ManualViewer
                                        selectedCitation={selectedCitation}
                                        defaultDoc="Manuale_Euro_VP_Manutenzione.pdf"
                                    />
                                </div>
                            </div>
                        )}
                    </main>

                    {/* Bottom Tab Bar (Matching exactly the Official UI/UX Sketch) */}
                    <nav className="mobile-tab-bar">
                        <button
                            className={`tab-item-rugged ${activeTab === 'chat' ? 'active' : ''}`}
                            onClick={() => setActiveTab('chat')}
                            aria-label="Chat Macchina"
                        >
                            <MessageSquare size={20} />
                            <span className="tab-label-text">Chat Macchina</span>
                        </button>

                        <button
                            className={`tab-item-rugged ${activeTab === 'manuals' ? 'active' : ''}`}
                            onClick={() => setActiveTab('manuals')}
                            aria-label="Documentazione"
                        >
                            <BookOpen size={20} />
                            <span className="tab-label-text">Manuale PDF</span>
                        </button>

                        <button
                            className="tab-item-rugged new-scan-tab"
                            onClick={handleNewScan}
                            aria-label="Nuova Scansione"
                        >
                            <QrCode size={20} />
                            <span className="tab-label-text">Nuova Scansione</span>
                        </button>
                    </nav>
                </div>
            )}
        </div>
    );
}