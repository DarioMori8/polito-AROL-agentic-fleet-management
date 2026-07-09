import React, { useState, useEffect } from 'react';
import { MessageSquare, LineChart, BookOpen, RotateCcw } from 'lucide-react';
import { useMachine } from '../context/MachineContext';
import ChatWindow from '../components/chat/ChatWindow';
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
    onSuggestionClick
}) {
    const { activeMachine, isScanned, clearMachine } = useMachine();

    // Mobile Tab State: 'chat' | 'iot' | 'manuals'
    const [activeTab, setActiveTab] = useState('chat');

    // Selected citation state passed to the ManualViewer
    const [selectedCitation, setSelectedCitation] = useState(null);

    // Tablet/Desktop Split-Screen state: true = split, false = tabbed
    const [isTabletLayout, setIsTabletLayout] = useState(window.innerWidth >= 768);

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
        clearMachine();
        if (onBackClick) {
            onBackClick(); // Redirects to fleet or camera view
        }
    };

    return (
        <div className={`workspace-container ${isTabletLayout ? 'tablet-split' : 'mobile-single'}`}>

            {/* ==========================================
         LAYOUT 1: TABLET SPLIT SCREEN (Multi-Column)
         ========================================== */}
            {isTabletLayout ? (
                <div className="split-layout-wrapper">
                    {/* Left Column: Fixed Conversational Stream */}
                    <aside className="split-column split-left">
                        <ChatWindow
                            messages={messages}
                            activeMachine={activeMachine}
                            isLoading={isLoading}
                            onSendMessage={onSendMessage}
                            onSuggestionClick={onSuggestionClick}
                            onBackClick={onBackClick}
                            onCitationClick={handleCitationClick}
                        />
                    </aside>

                    {/* Right Column: Contextual Pane (IoT / Manual PDF) */}
                    <main className="split-column split-right">
                        <div className="split-right-header">
                            <button
                                className={`pane-tab-btn ${activeTab === 'iot' ? 'active' : ''}`}
                                onClick={() => setActiveTab('iot')}
                            >
                                <LineChart size={16} />
                                Telemetria IoT Real-Time
                            </button>
                            <button
                                className={`pane-tab-btn ${activeTab === 'manuals' ? 'active' : ''}`}
                                onClick={() => setActiveTab('manuals')}
                            >
                                <BookOpen size={16} />
                                Manuale Tecnico & PDF
                            </button>
                        </div>

                        <div className="pane-content-viewport">
                            {activeTab === 'iot' || activeTab === 'chat' ? (
                                /* IoT Dashboard Mock Skeleton (Fase 0/1 Compliance) */
                                <div className="pane-skeleton iot-skeleton">
                                    <div className="skeleton-kpi-grid">
                                        <div className="skeleton-kpi-card">
                                            <span className="kpi-label">TEMPERATURA BASAMENTO</span>
                                            <span className="kpi-value warning">68.4 °C</span>
                                            <span className="kpi-status">Soglia critica superata</span>
                                        </div>
                                        <div className="skeleton-kpi-card">
                                            <span className="kpi-label">COPPIA DI SERRAGGIO</span>
                                            <span className="kpi-value success">14.2 Nm</span>
                                            <span className="kpi-status">Valore ottimale</span>
                                        </div>
                                    </div>
                                    <div className="skeleton-chart-container">
                                        <span className="chart-placeholder-text">Grafico IoT Temporale (In fase di sviluppo...)</span>
                                    </div>
                                </div>
                            ) : (
                                /* Manual Viewer Mock Skeleton (Fase 0/1 Compliance) */
                                <div className="pane-skeleton manuals-skeleton">
                                    <div className="pdf-viewer-header">
                                        <BookOpen size={18} style={{ color: 'var(--arol-sky)' }} />
                                        <span className="pdf-title">
                                            {selectedCitation ? selectedCitation.docName : 'Seleziona una citazione per visualizzare il capitolo'}
                                        </span>
                                        {selectedCitation?.page && (
                                            <span className="pdf-page-indicator">Pagina {selectedCitation.page}</span>
                                        )}
                                    </div>
                                    <div className="pdf-canvas-mock">
                                        {selectedCitation ? (
                                            <div className="pdf-extracted-page-text">
                                                <h4>CAPITOLO 4.2 - RISOLUZIONE DELLE VIBRAZIONI ANOMALE (PAG. {selectedCitation.page})</h4>
                                                <p>
                                                    [ESTRATTO DAL MANUALE DI SINTESI RAG] ...In presenza di una vibrazione oscillante registrata sull'asse primario
                                                    del tappatore Euro VP, ispezionare il serraggio dei rulli folli. La coppia di serraggio standard non deve
                                                    scendere sotto la soglia di 14 Nm...
                                                </p>
                                                <span className="rag-grounding-marker">Fonte verificata dal Manuals Agent</span>
                                            </div>
                                        ) : (
                                            <div className="pdf-empty-prompt">
                                                <BookOpen size={48} className="deco-icon" />
                                                <p>Tocca un badge di citazione della chat RAG (es: Manuale p. 24) per caricare istantaneamente la pagina esatta del documento.</p>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
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
                            <ChatWindow
                                messages={messages}
                                activeMachine={activeMachine}
                                isLoading={isLoading}
                                onSendMessage={onSendMessage}
                                onSuggestionClick={onSuggestionClick}
                                onBackClick={onBackClick}
                                onCitationClick={handleCitationClick}
                            />
                        )}

                        {activeTab === 'iot' && (
                            <div className="mobile-pane-wrapper">
                                <header className="mobile-pane-header">
                                    <h2>Telemetria Real-Time</h2>
                                    <span className="machine-tag">{activeMachine.name}</span>
                                </header>
                                <div className="pane-content-viewport">
                                    <div className="pane-skeleton iot-skeleton">
                                        <div className="skeleton-kpi-grid">
                                            <div className="skeleton-kpi-card">
                                                <span className="kpi-label">TEMPERATURA BASAMENTO</span>
                                                <span className="kpi-value warning">68.4 °C</span>
                                            </div>
                                            <div className="skeleton-kpi-card">
                                                <span className="kpi-label">COPPIA DI SERRAGGIO</span>
                                                <span className="kpi-value success">14.2 Nm</span>
                                            </div>
                                        </div>
                                        <div className="skeleton-chart-container">
                                            <span className="chart-placeholder-text">Visualizzazione Grafico IoT</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {activeTab === 'manuals' && (
                            <div className="mobile-pane-wrapper">
                                <header className="mobile-pane-header">
                                    <h2>Manuale d'Uso & RAG</h2>
                                    <span className="machine-tag">{activeMachine.name}</span>
                                </header>
                                <div className="pane-content-viewport">
                                    <div className="pane-skeleton manuals-skeleton">
                                        <div className="pdf-viewer-header">
                                            <BookOpen size={16} />
                                            <span className="pdf-title-text">
                                                {selectedCitation ? selectedCitation.docName : 'Seleziona una citazione'}
                                            </span>
                                        </div>
                                        <div className="pdf-canvas-mock">
                                            {selectedCitation ? (
                                                <div className="pdf-extracted-page-text">
                                                    <h4>CAPITOLO (PAG. {selectedCitation.page})</h4>
                                                    <p>
                                                        ...Estratto testuale simulato per l'operatore mobile. Il testo corrisponde alla pagina {selectedCitation.page} del manuale tecnico di fabbrica...
                                                    </p>
                                                </div>
                                            ) : (
                                                <div className="pdf-empty-prompt">
                                                    <p>Nessun documento caricato. Clicca sulle fonti citate nella chat per aprire il manuale tecnico.</p>
                                                </div>
                                            )}
                                        </div>
                                    </div>
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
                            className={`tab-item-rugged ${activeTab === 'iot' ? 'active' : ''}`}
                            onClick={() => setActiveTab('iot')}
                            aria-label="IoT Telemetria"
                        >
                            <LineChart size={20} />
                            <span className="tab-label-text">Parametri IoT</span>
                        </button>

                        <button
                            className="tab-item-rugged new-scan-tab"
                            onClick={handleNewScan}
                            aria-label="Nuova Scansione"
                        >
                            <RotateCcw size={20} />
                            <span className="tab-label-text">Nuova Scansione</span>
                        </button>
                    </nav>
                </div>
            )}
        </div>
    );
}