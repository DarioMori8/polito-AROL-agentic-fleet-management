import React, { useEffect, useState } from 'react';
import { QrCode, ShieldAlert, Cpu, RefreshCw, ArrowLeft } from 'lucide-react';
import { useMachine } from '../context/MachineContext';
import Button from '../components/ui/Button';
import '../styles/LandingQR.css';

/**
 * LandingQR Page Component.
 * Associated with the route "/machine/:id".
 * Automatically triggered when a plant operator scans a QR code on an AROL machine.
 * It resolves the machine ID, updates the global MachineContext, and transitions to the ChatWorkspace.
 * Directly extract the ID from route parameters (or make the parsing of the URL route as resilient fallback for mobile PWA).
 */
export default function LandingQR({ machineIdFromRoute, onScanSuccess, onNavigateToFleet }) {
    const { activeMachine, loading, error, scanMachine, clearMachine } = useMachine();
    const [localMachineId, setLocalMachineId] = useState('');
    const [showManualInput, setShowManualInput] = useState(false);

    // Extract ID from URL path if not explicitly passed as a prop (robust fallback for mobile PWAs)
    const resolvedId = machineIdFromRoute || (() => {
        const pathParts = window.location.pathname.split('/');
        const lastPart = pathParts[pathParts.length - 1];
        // Simple check to ensure we got a potential ID and not the route name
        return (lastPart && lastPart !== 'machine') ? lastPart : null;
    })();

    // Trigger RAG/IoT context resolution when the machine ID is detected
    useEffect(() => {
        if (resolvedId) {
            scanMachine(resolvedId);
        }
    }, [resolvedId]);

    // Handle successful scan routing transition
    useEffect(() => {
        if (activeMachine && !loading && !error) {
            if (onScanSuccess) {
                // Triggers parent transition to ChatWorkspace
                onScanSuccess(activeMachine.id);
            }
        }
    }, [activeMachine, loading, error]);

    const handleManualSubmit = (e) => {
        e.preventDefault();
        if (localMachineId.trim()) {
            scanMachine(localMachineId.trim());
        }
    };

    const handleGoBack = () => {
        clearMachine();
        if (onNavigateToFleet) {
            onNavigateToFleet();
        }
    };

    return (
        <div className="landing-qr-layout">
            {/* Background industrial graphic pattern */}
            <div className="industrial-mesh-overlay"></div>

            <div className="landing-card-container">
                {/* Top Header - Brand Logo */}
                <header className="landing-logo-header">
                    <div className="brand-badge">AROL Group</div>
                    <h2 className="platform-sub-title">Multi-Agent Conversational Platform</h2>
                </header>

                <main className="landing-main-content">
                    {/* STATE 1: LOADING / RESOLVING QR TAG */}
                    {loading && (
                        <div className="landing-state-view state-loading">
                            <div className="spinner-wrapper-rugged">
                                <RefreshCw size={40} className="spinning-icon" />
                            </div>
                            <h3 className="state-headline">Risoluzione Codice QR</h3>
                            <p className="state-subtext">
                                Connessione sicura al Gateway AROL IoT in corso...<br />
                                Recupero parametri macchina e manuali tecnici.
                            </p>
                            <div className="tag-pulse-indicator">
                                <span className="dot-pulse"></span>
                                <span className="tag-label">ID: {resolvedId || 'Rilevamento...'}</span>
                            </div>
                        </div>
                    )}

                    {/* STATE 2: ERROR - UNABLE TO RESOLVE TAG OR MACHINE NOT FOUND */}
                    {error && !loading && (
                        <div className="landing-state-view state-error">
                            <div className="error-icon-wrapper">
                                <ShieldAlert size={48} className="error-icon" />
                            </div>
                            <h3 className="state-headline text-danger">Errore di Risoluzione</h3>
                            <p className="state-subtext">
                                Impossibile identificare il macchinario. Il codice QR potrebbe essere danneggiato o non registrato nella flotta AROL.
                            </p>

                            <div className="error-details-box">
                                <strong>Dettaglio errore:</strong> {error}
                            </div>

                            {/* Manual Input Toggle for Rugged UI redundancy */}
                            {!showManualInput ? (
                                <div className="action-buttons-stack">
                                    <Button variant="primary" onClick={() => setShowManualInput(true)} className="w-full">
                                        Inserisci ID Manualmente
                                    </Button>
                                    <Button variant="outline" onClick={handleGoBack} className="w-full">
                                        <ArrowLeft size={16} style={{ marginRight: '8px' }} />
                                        Torna alla Flotta Macchine
                                    </Button>
                                </div>
                            ) : (
                                <form onSubmit={handleManualSubmit} className="manual-input-form">
                                    <label htmlFor="machine-id-input" className="form-label">
                                        Digita il Codice Identificativo (ID)
                                    </label>
                                    <div className="form-input-row">
                                        <input
                                            id="machine-id-input"
                                            type="text"
                                            placeholder="Es. 001, 002, 003"
                                            value={localMachineId}
                                            onChange={(e) => setLocalMachineId(e.target.value)}
                                            className="rugged-text-input"
                                            required
                                        />
                                        <Button type="submit" variant="secondary" className="input-submit-btn">
                                            Verifica
                                        </Button>
                                    </div>
                                    <button
                                        type="button"
                                        className="cancel-link-btn"
                                        onClick={() => setShowManualInput(false)}
                                    >
                                        Annulla
                                    </button>
                                </form>
                            )}
                        </div>
                    )}

                    {/* STATE 3: DEFAULT SCANNED GATEWAY (Waiting for URL scan trigger) */}
                    {!resolvedId && !loading && !error && (
                        <div className="landing-state-view state-scan-prompt">
                            <div className="qr-scanner-illustration">
                                <QrCode size={64} className="qr-icon-deco" />
                                <div className="scanning-laser-line"></div>
                            </div>
                            <h3 className="state-headline">In Attesa di Scansione</h3>
                            <p className="state-subtext">
                                Inquadra il QR code posizionato sul carter o sulla pulsantiera principale della macchina AROL per avviare il supporto AI in tempo reale.
                            </p>
                            <div className="manual-access-section">
                                <span className="divider-text">Oppure</span>
                                <Button variant="secondary" onClick={() => setShowManualInput(true)} className="w-full">
                                    Inserisci ID Macchina Manualmente
                                </Button>
                                <Button variant="outline" onClick={handleGoBack} className="w-full" style={{ marginTop: '12px' }}>
                                    Visualizza Tutta la Flotta
                                </Button>
                            </div>

                            {showManualInput && (
                                <form onSubmit={handleManualSubmit} className="manual-input-form" style={{ marginTop: '20px' }}>
                                    <label htmlFor="machine-id-input" className="form-label">
                                        Inserisci ID Macchinario
                                    </label>
                                    <div className="form-input-row">
                                        <input
                                            id="machine-id-input"
                                            type="text"
                                            placeholder="Es. 001, 002..."
                                            value={localMachineId}
                                            onChange={(e) => setLocalMachineId(e.target.value)}
                                            className="rugged-text-input"
                                            required
                                        />
                                        <Button type="submit" variant="primary" className="input-submit-btn">
                                            Invia
                                        </Button>
                                    </div>
                                </form>
                            )}
                        </div>
                    )}
                </main>

                <footer className="landing-corporate-footer">
                    <p>© 2026 AROL Group S.p.A. • Canelli (AT)</p>
                    <span className="footer-doc-link">Industrial Smart Factory Platform</span>
                </footer>
            </div>
        </div>
    );
}