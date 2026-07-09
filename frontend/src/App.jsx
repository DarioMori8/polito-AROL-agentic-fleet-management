import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useParams } from 'react-router';
import { useMachine } from './context/MachineContext';
import LandingQR from './pages/LandingQR';
import ChatWorkspace from './pages/ChatWorkspace';
import { Cpu, ShieldAlert, CheckCircle2, Search } from 'lucide-react';
import './styles/App.css';

// TO BE MOVED IN SEPARATE FILE
/**
 * FleetView Component
 * Renders the dashboard showing all available machinery in the industrial fleet.
 * Allows searching, filtering, and clicking a machine card to simulate a QR scan.
 */
function FleetView() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');

  // TO BE REMOVED
  // Hardcoded fleet database based on design specifications
  const fleetMachines = [
    { id: '001', name: 'AROL Capper #12', dept: 'Reparto Imbottigliamento', status: 'In Allarme', code: 'AR-CAP12' },
    { id: '002', name: 'AROL Labeller #4', dept: 'Reparto Etichettatura', status: 'Operativo', code: 'AR-LAB04' },
    { id: '003', name: 'AROL Filler #9', dept: 'Reparto Riempimento', status: 'Operativo', code: 'AR-FIL09' },
  ];

  const filteredFleet = fleetMachines.filter(m => {
    const matchesSearch = m.name.toLowerCase().includes(searchQuery.toLowerCase()) || m.id.includes(searchQuery);
    if (activeFilter === 'all') return matchesSearch;
    if (activeFilter === 'ok') return matchesSearch && (m.status === 'Operativo');
    if (activeFilter === 'alarm') return matchesSearch && (m.status === 'In Allarme');
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
      </header>

      <main className="fleet-main">
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
          <button
            className={`filter-chip ${activeFilter === 'all' ? 'active' : ''}`}
            onClick={() => setActiveFilter('all')}
          >
            Tutti
          </button>
          <button
            className={`filter-chip ${activeFilter === 'ok' ? 'active' : ''}`}
            onClick={() => setActiveFilter('ok')}
          >
            Operativi
          </button>
          <button
            className={`filter-chip ${activeFilter === 'alarm' ? 'active' : ''}`}
            onClick={() => setActiveFilter('alarm')}
          >
            In Errore
          </button>
        </div>

        {/* Fleet Card Grid */}
        <div className="fleet-grid">
          {filteredFleet.map((machine) => (
            <div
              key={machine.id}
              className={`machine-card-rugged ${machine.status === 'In Allarme' ? 'border-alarm' : ''}`}
              onClick={() => handleMachineClick(machine.id)}
              style={{ touchAction: 'manipulation' }}
            >
              <div className="card-hardware-icon-wrapper">
                <Cpu size={24} />
              </div>

              <div className="card-info">
                <h3 className="card-machine-name">{machine.name}</h3>
                <span className="card-machine-id">ID: {machine.id} ({machine.code})</span>
                <span className="card-machine-dept">{machine.dept}</span>

                <div className="card-status-row">
                  {machine.status === 'In Allarme' ? (
                    <span className="card-badge badge-error">
                      <ShieldAlert size={12} style={{ marginRight: '4px' }} />
                      Stato: In Allarme
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
// TO BE MODIFIED WHEN REAL BACKEND CHAT HANDLERS IMPLEMENTED
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

  // Trigger Context load if the user types or deep-links directly into the workspace URL
  useEffect(() => {
    if (id && (!activeMachine || activeMachine.id !== id)) {
      scanMachine(id);
    }
  }, [id, activeMachine]);

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

  const handleSendMessage = (messageData) => {
    const userMessageTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const newUserMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: messageData.text,
      timestamp: userMessageTime,
      status: 'sent'
    };

    setMessages((prev) => [...prev, newUserMessage]);
    setIsAiLoading(true);

    // Simulated RAG agents response (DoD Phase 0/1 compliance)
    setTimeout(() => {
      let aiResponseText = '';
      let citations = [];
      let confidence = 0.85;

      const lowerText = messageData.text.toLowerCase();

      if (lowerText.includes('vibraz') || lowerText.includes('guasti') || lowerText.includes('troubleshoot')) {
        aiResponseText = `Il **Troubleshoot Agent** rileva anomalie vibratorie sul basamento primario.\n- Verificare immediatamente la coppia di serraggio dei bulloni di ancoraggio.\n- Controllare lo stato di usura dei rulli folli di scorrimento.\n- Se la vibrazione persiste, spegnere la linea e allineare la camma di chiusura.`;
        citations = [
          { docName: 'Manuale_Euro_VP_Manutenzione.pdf', page: 42 },
          { docName: 'Specifiche_Ancoraggio_AROL.pdf', page: 15 }
        ];
        confidence = 0.94;
      } else if (lowerText.includes('manual') || lowerText.includes('consult')) {
        aiResponseText = `Ho interrogato il **Manuals Agent** tramite MCP Server.\nI manuali d'uso indicano che la manutenzione preventiva sui rulli folli del modello **${activeMachine.modelType}** deve avvenire ogni 500 ore lavorative o all'apparire del codice allarme AL-VIB-02.`;
        citations = [
          { docName: 'Manuale_Euro_VP_Manutenzione.pdf', page: 24 }
        ];
        confidence = 0.89;
      } else if (lowerText.includes('iot') || lowerText.includes('telemetria') || lowerText.includes('dati')) {
        aiResponseText = `Il **Telemetry Agent** comunica la presenza di un picco termico sui sensori del motore principale:\n- Temperatura basamento: **68.4 °C** (Soglia limite: 60 °C)\n- Coppia di serraggio: **14.2 Nm** (Normale)\n\nSi consiglia di monitorare le vibrazioni o avviare un ciclo di lubrificazione manuale.`;
        citations = [
          { docName: 'Specifiche_Serraggio_Q2.pdf', page: 8 }
        ];
        confidence = 0.97;
      } else {
        aiResponseText = `Ho ricevuto la tua richiesta: "${messageData.text}".\nSto analizzando i dati della flotta con il supporto degli agenti AROL AI. Puoi selezionare una delle scorciatoie rapide per richiedere guide diagnostiche o telemetrie istantanee.`;
        confidence = 0.75;
      }

      const newAiMessage = {
        id: `ai-${Date.now()}`,
        sender: 'assistant',
        text: aiResponseText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        status: 'sent',
        citations: citations,
        metadata: { confidence: confidence }
      };

      setMessages((prev) => [...prev, newAiMessage]);
      setIsAiLoading(false);
    }, 1200);
  };

  const handleSuggestionClick = (chipId, actionText) => {
    handleSendMessage({ text: actionText });
  };

  const handleBackToFleet = () => {
    setMessages([]);
    navigate('/');
  };

  return (
    <ChatWorkspace
      messages={messages}
      isLoading={isAiLoading}
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
  );
}