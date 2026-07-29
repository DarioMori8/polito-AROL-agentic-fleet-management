import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useParams } from 'react-router';
import { MachineProvider, useMachine } from './context/MachineContext';
import LandingQR from './pages/LandingQR';
import ChatWorkspace from './pages/ChatWorkspace';
import { Cpu, ShieldAlert, CheckCircle2, Search, RefreshCw } from 'lucide-react';
import './styles/App.css';
import useChatApi from './hooks/useChatApi';

// TO BE MOVED IN SEPARATE FILE
/**
 * FleetView Component
 * Renders the dashboard showing all available machinery in the industrial fleet.
 * Allows searching, filtering, and clicking a machine card to simulate a QR scan.
 */
function FleetView() {
  const navigate = useNavigate();
  const { fleet, loading, error, fetchFleet } = useMachine();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');

  // Trigger fleet load from server on mount
  useEffect(() => {
    fetchFleet();
  }, [fetchFleet]);

  // Status mappings: 'online' -> Operating, others -> In Alarm / Under Maintenance
  const filteredFleet = fleetMachines.filter(m => {
    const matchesSearch = m.name.toLowerCase().includes(searchQuery.toLowerCase()) || m.id.includes(searchQuery);
    if (activeFilter === 'all') return matchesSearch;
    if (activeFilter === 'ok') return matchesSearch && (m.status === 'online');
    if (activeFilter === 'alarm') return matchesSearch && (m.status !== 'online');
    return matchesSearch;
  });

  const handleMachineClick = (id) => {
    // Navigate dynamically to the scanned machine landing resolver
    navigate(`/machine/${id}`);
  };

  return (
    <div className="fleet-view-container">
      <header className="fleet-header">
        <div className="fleet-brand">AROL Group</div>
        <h1 className="fleet-title">Flotta Macchinari</h1>
        <p className="fleet-subtitle">Digital Fleet Portal & Asset Control</p>

        {/* Dynamic Sync Trigger (WCAG Touch target compliant) */}
        <button className="sync-fleet-btn" onClick={fetchFleet} disabled={loading} style={{ touchAction: 'manipulation' }}>
          <RefreshCw size={14} className={loading ? 'spinning-icon' : ''} />
          <span>Sincronizza Rete</span>
        </button>
      </header>

      <main className="fleet-main">
        {/* Connection Failure Toast Alert */}
        {error && (
          <div className="connection-error-banner">
            <AlertTriangle size={16} />
            <span>{error}</span>
          </div>
        )}


        {/* Search Input Bar (Rugged Touch Target) */}
        <div className="search-bar-rugged">
          <Search className="search-icon" size={18} />
          <input
            type="text"
            placeholder="Cerca per macchinario o ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input-rugged"
          />
        </div>

        {/* Filter Selection Row */}
        <div className="filter-chips-row">
          <button className={`filter-chip ${activeFilter === 'all' ? 'active' : ''}`} onClick={() => setActiveFilter('all')}>
            Tutti ({fleet.length})
          </button>
          <button className={`filter-chip ${activeFilter === 'ok' ? 'active' : ''}`} onClick={() => setActiveFilter('ok')}>
            Operativi ({fleet.filter(m => m.status === 'online').length})
          </button>
          <button className={`filter-chip ${activeFilter === 'alarm' ? 'active' : ''}`} onClick={() => setActiveFilter('alarm')}>
            In Errore ({fleet.filter(m => m.status !== 'online').length})
          </button>
        </div>

        {loading && fleet.length === 0 ? (
          <div className="fleet-loading-view">
            <RefreshCw size={36} className="spinning-icon" />
            <p>Interrogazione database macchinari in corso...</p>
          </div>
        ) : (
          <div className="fleet-grid"> {/* Fleet Card Grid */}
            {filteredFleet.map((machine) => (
              <div
                key={machine.id}
                className={`machine-card-rugged ${machine.status !== 'online' ? 'border-alarm' : ''}`}
                onClick={() => handleMachineClick(machine.id)}
                style={{ touchAction: 'manipulation' }}
              >
                <div className="card-hardware-icon-wrapper">
                  <Cpu size={24} />
                </div>

                <div className="card-info">
                  <h3 className="card-machine-name">{machine.name}</h3>
                  <span className="card-machine-id">ID: {machine.id} ({machine.model || 'Standard'})</span>
                  <span className="card-machine-dept">S/N: {machine.serial_number || 'N/D'} • {machine.location}</span>

                  <div className="card-status-row">
                    {machine.status !== 'online' ? (
                      <span className="card-badge badge-error">
                        <ShieldAlert size={12} style={{ marginRight: '4px' }} />
                        Stato: {machine.status === 'maintenance' ? 'Manutenzione' : 'Offline'}
                      </span>
                    ) : (
                      <span className="card-badge badge-success">
                        <CheckCircle2 size={12} style={{ marginRight: '4px' }} />
                        Stato: Operativo
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      <footer className="fleet-footer">
        <p>© 2026 AROL Group S.p.A. • Canelli (AT)</p>
        <span className="footer-system-tag">Smart Factory Agentic Fleet</span>
      </footer>
    </div>
  );
}

// TO BE MOVED IN SEPARATE FILE
/**
 * LandingResolver Component
 * Simple intermediate route component to extract parameters and render LandingQR
 */
function LandingResolver() {
  const { id } = useParams();
  const navigate = useNavigate();

  const handleScanSuccess = (machineId) => {
    // Navigate directly to the conversational workspace upon success
    navigate(`/workspace/${machineId}`);
  };

  const handleNavigateToFleet = () => {
    navigate('/');
  };

  return (
    <LandingQR
      machineIdFromRoute={id}
      onScanSuccess={handleScanSuccess}
      onNavigateToFleet={handleNavigateToFleet}
    />
  );
}

// TO BE MOVED IN SEPARATE FILE
/**
 * WorkspaceWrapper Component
 * Handles conversational mock API states and feeds ChatWorkspace based on URL route ID
 */
function WorkspaceWrapper() {
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
    if (activeMachine && activeMachine.id === id) {
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
      isLoading={isStreaming}
      onSendMessage={handleSendMessage}
      onSuggestionClick={handleSuggestionClick}
      onBackClick={handleBackToFleet}
    />
  );
}

/**
 * Root Entry Point with standard React Router configuration
 */
export default function App() {
  return (
    <MachineProvider>
      <Router>
        <div className="app-viewport">
          <Routes>
            {/* Main Fleet View Route */}
            <Route path="/" element={<FleetView />} />
            <Route path="/fleet" element={<FleetView />} />

            {/* QR Scan Landing and Resolution Route */}
            <Route path="/machine/:id" element={<LandingResolver />} />

            {/* Conversational and Diagnostic Workspace Route */}
            <Route path="/workspace/:id" element={<WorkspaceWrapper />} />
          </Routes>
        </div>
      </Router>
    </MachineProvider>
  );
}