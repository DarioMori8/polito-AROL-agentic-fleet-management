import React, { useState, useEffect, useRef } from 'react';
import { useMachine } from '@/context/MachineContext';
import {
    BookOpen,
    ChevronLeft,
    ChevronRight,
    ZoomIn,
    ZoomOut,
    Maximize2,
    Minimize2,
    Search,
    Copy,
    Check,
    FileText,
    Sliders,
    AlertTriangle
} from 'lucide-react';
import '@/styles/ManualViewer.css';

// TO BE REMOVED WHEN REAL MANUAL DATABASE IMPLEMENTED
// Rich fallback technical documentation database for in-field simulation (Fase 1/2 DoD)
const FALLBACK_MANUALS_DATABASE = {
    'Manuale_Euro_VP_Manutenzione.pdf': {
        title: 'AROL Euro VP - Use & Maintenance Manual',
        totalPages: 80,
        pages: {
            24: {
                section: 'Section 4.1 - Preventive Maintenance Scheduler',
                title: 'IDLE ROLLERS LUBRICATION & SERVICE INTERVALS',
                text: 'Routine inspection and lubrication of the idle rollers on the Euro VP capping head must be conducted every 500 operating hours. In high-humidity bottling lines, reduce this interval to 300 hours. Immediate manual lubrication is mandatory if the telemetry system triggers the vibration alarm AL-VIB-02.',
                specs: [
                    { label: 'Lubricant Type', value: 'AROL Food-Grade Grease Synthetic-3' },
                    { label: 'Check Interval', value: '500 Hours (Standard) / 300 Hours (Wet environment)' },
                    { label: 'Related Alarm', value: 'AL-VIB-02 (Vibration Out of Range)' }
                ],
                blueprintType: 'roller'
            },
            42: {
                section: 'Section 4.2 - Vibration Diagnostics',
                title: 'VIBRATION ANOMALIES & CAM ALIGNMENT',
                text: 'Excessive baseplate vibration often originates from loose anchoring bolts or uneven pressure distribution along the capping track. Inspect the idle guide rollers for structural wear. Tighten anchor bolts to the certified specifications. If vibrations continue to exceed threshold limits, check and manually align the main capping closing cam.',
                specs: [
                    { label: 'Primary Cam Clearances', value: '0.05 mm - 0.12 mm' },
                    { label: 'Anchor Bolt Torque', value: '120.0 Nm' },
                    { label: 'Inspection Points', value: 'Capping Head Basement, Idle Guide Rollers, Roller Bearings' }
                ],
                blueprintType: 'cam'
            }
        }
    },
    'Specifiche_Ancoraggio_AROL.pdf': {
        title: 'AROL Structural Anchoring & Installation Specs',
        totalPages: 30,
        pages: {
            15: {
                section: 'Section 2.3 - Heavy Duty Anchoring',
                title: 'BASEPLATE STABILIZATION & MECHANICAL ANCHORING',
                text: 'To minimize operational harmonics and high-torque mechanical resonance, capping machines must be rigidly bolted using M16 class 8.8 threaded anchors. The concrete foundation must be fully cured (min. 28 days) with a minimum compressive strength of 25 MPa. Ensure uniform torque distribution using a calibrated torque wrench.',
                specs: [
                    { label: 'Bolt Spec', value: 'M16 Threaded Rod, Class 8.8 Steel' },
                    { label: 'Target Tightening Torque', value: '120.0 Nm (±5 Nm Tolerance)' },
                    { label: 'Minimum Concrete Depth', value: '150.0 mm' }
                ],
                blueprintType: 'anchor'
            }
        }
    },
    'Specifiche_Serraggio_Q2.pdf': {
        title: 'AROL Mechanical Torque & Thermal Tolerances',
        totalPages: 18,
        pages: {
            8: {
                section: 'Section 1.8 - Motor Thermal Thresholds',
                title: 'MOTOR THERMAL LIMITS & CAPPING TORQUE COEFFICIENTS',
                text: 'The main motor drive assembly is designed to operate continuously under a baseplate temperature limit of 60.0 °C. Exceeding 65.0 °C triggers automatic telemetry warnings. Capping torque coefficients for the Euro VP capping jaws must be maintained at an optimal value of 14.2 Nm to prevent bottle closure deformation or leakage.',
                specs: [
                    { label: 'Max Baseplate Temp', value: '60.0 °C (Operational Limit) / 65.0 °C (Critical Threshold)' },
                    { label: 'Optimal Capping Torque', value: '14.2 Nm' },
                    { label: 'Power Supply Coefficient', value: '400V / 50Hz (Stabilized)' }
                ],
                blueprintType: 'motor'
            }
        }
    }
};

/**
 * ManualViewer Component (Context Aware & Dynamic)
 *
 * Sinks directly into AROL's MachineContext to dynamically fetch and display real
 * technical manuals retrieved via 'GET /v1/machines/{id}/manuals'.
 * 
 * If citations are passed from the conversational RAG engine, it overrides active document
 * selections, jumps to the exact page, and renders the live retrieved Vector DB snippet
 * within an engineering blueprint canvas.
 */
export default function ManualViewer({ selectedCitation = null, defaultDoc = 'Manuale_Euro_VP_Manutenzione.pdf' }) {
    const { activeManuals, activeMachine } = useMachine();

    // Navigation & document states
    const [activeDocName, setActiveDocName] = useState(defaultDoc);
    const [currentPage, setCurrentPage] = useState(24);
    const [zoom, setZoom] = useState(100); // Zoom percentage (70% - 150%)
    const [isFullscreen, setIsFullscreen] = useState(false);

    // Search state
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [showSearchPanel, setShowSearchPanel] = useState(false);

    // Utility states
    const [copied, setCopied] = useState(false);
    const viewerRef = useRef(null);

    // Determine current active list of manuals (Server-loaded vs Offline fallback)
    const isUsingFallback = !activeManuals || activeManuals.length === 0;
    const manualsList = isUsingFallback
        ? Object.keys(FALLBACK_MANUALS_DATABASE).map(filename => ({
            filename,
            title: FALLBACK_MANUALS_DATABASE[filename].title,
            page_count: FALLBACK_MANUALS_DATABASE[filename].totalPages
        }))
        : activeManuals;

    // Settle on an initial active document when manuals are retrieved or modified
    useEffect(() => {
        if (manualsList.length > 0) {
            // If our current doc is not in the list, set the first available manual
            const docExists = manualsList.some(m => m.filename === activeDocName);
            if (!docExists) {
                setActiveDocName(manualsList[0].filename);
                setCurrentPage(1);
            }
        }
    }, [manualsList, activeDocName]);

    // Sync state when a user clicks on an AI citation in the chat (Inter-component communication)
    useEffect(() => {
        if (selectedCitation && selectedCitation.docName) {
            const matchExists = manualsList.some(m => m.filename === selectedCitation.docName);
            if (matchExists) {
                setActiveDocName(selectedCitation.docName);
                setCurrentPage(selectedCitation.page || 1);
            } else {
                // Safe check for offline match
                if (FALLBACK_MANUALS_DATABASE[selectedCitation.docName]) {
                    setActiveDocName(selectedCitation.docName);
                    setCurrentPage(selectedCitation.page || 1);
                }
            }
        }
    }, [selectedCitation, manualsList]);

    // Retrieve current active manual details
    const activeManualRecord = manualsList.find(m => m.filename === activeDocName);
    const totalPagesCount = activeManualRecord ? activeManualRecord.page_count : 100;

    // Parse page content either from fallback database or inject real RAG snippet
    const getPageContent = () => {
        // 1. Check if we have pre-defined mock page data matching this file & page
        const fallbackDoc = FALLBACK_MANUALS_DATABASE[activeDocName];
        if (fallbackDoc && fallbackDoc.pages[currentPage]) {
            const fallbackPage = fallbackDoc.pages[currentPage];

            // If the user clicked on this specific page as a RAG citation and it has a live snippet, 
            // we enrich the page content with the real Vector DB chunk dynamically!
            if (selectedCitation && selectedCitation.docName === activeDocName && selectedCitation.page === currentPage && selectedCitation.snippet) {
                return {
                    ...fallbackPage,
                    text: selectedCitation.snippet, // Real LLM/Chroma chunk injected!
                    isSnippetInjected: true
                };
            }
            return fallbackPage;
        }

        // 2. If no mock blueprint exists for this file/page, but we have a live active citation snippet, we draw it!
        if (selectedCitation && selectedCitation.docName === activeDocName && selectedCitation.page === currentPage && selectedCitation.snippet) {
            return {
                section: 'AI RAG Retrieved Segment',
                title: 'LIVE VECTOR DB DOCUMENT EXTRACT',
                text: selectedCitation.snippet,
                specs: [
                    { label: 'Source File', value: activeDocName },
                    { label: 'Reference Page', value: `${currentPage}` },
                    { label: 'Database Segment', value: 'ChromaDB Active Chunk' }
                ],
                blueprintType: 'default',
                isSnippetInjected: true
            };
        }

        // 3. Fallback standard page view for non-indexed pages
        return {
            section: 'Technical Instruction Sheet',
            title: 'AROL SYSTEM RUNTIME DOCUMENTATION',
            text: `This technical documentation segment is dynamically cataloged on the server. You are viewing page ${currentPage} of ${activeDocName}. Please consult the RAG chatbot to query specific troubleshooting procedures or maintenance thresholds from this manual.`,
            specs: [
                { label: 'Document Name', value: activeDocName },
                { label: 'Active Page', value: `${currentPage} / ${totalPagesCount}` },
                { label: 'Integration Status', value: isUsingFallback ? 'Offline Cache' : 'Active REST Endpoint' }
            ],
            blueprintType: 'default'
        };
    };

    const pageData = getPageContent();

    // Document Navigation
    const handleNextPage = () => {
        if (currentPage < totalPagesCount) {
            setCurrentPage((prev) => prev + 1);
        }
    };

    const handlePrevPage = () => {
        if (currentPage > 1) {
            setCurrentPage((prev) => prev - 1);
        }
    };

    const handleDocChange = (e) => {
        const docName = e.target.value;
        setActiveDocName(docName);
        setCurrentPage(1);
    };

    // Zoom Operations
    const handleZoomIn = () => setZoom((prev) => Math.min(prev + 10, 150));
    const handleZoomOut = () => setZoom((prev) => Math.max(prev - 10, 70));

    // Fullscreen toggle
    const toggleFullscreen = () => {
        if (!isFullscreen) {
            if (viewerRef.current?.requestFullscreen) {
                viewerRef.current.requestFullscreen();
            }
            setIsFullscreen(true);
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            }
            setIsFullscreen(false);
        }
    };

    // Listen for native escape keys to reset fullscreen state
    useEffect(() => {
        const handleFullscreenChange = () => {
            setIsFullscreen(!!document.fullscreenElement);
        };
        document.addEventListener('fullscreenchange', handleFullscreenChange);
        return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
    }, []);

    // Internal search engine (Searches through all documents and indexes matching pages)
    const handleSearch = (e) => {
        const query = e.target.value;
        setSearchQuery(query);
        if (!query.trim()) {
            setSearchResults([]);
            return;
        }

        const matches = [];

        // Search inside fallback database
        Object.entries(FALLBACK_MANUALS_DATABASE).forEach(([docKey, docVal]) => {
            Object.entries(docVal.pages).forEach(([pageNum, pageVal]) => {
                const textContent = `${pageVal.title} ${pageVal.text} ${pageVal.section}`.toLowerCase();
                if (textContent.includes(query.toLowerCase())) {
                    matches.push({
                        docName: docKey,
                        page: parseInt(pageNum, 10),
                        title: pageVal.title,
                        section: pageVal.section
                    });
                }
            });
        });

        // Also search active manuals index
        manualsList.forEach(m => {
            if (!FALLBACK_MANUALS_DATABASE[m.filename] && m.title.toLowerCase().includes(query.toLowerCase())) {
                matches.push({
                    docName: m.filename,
                    page: 1,
                    title: m.title,
                    section: 'Document Cover'
                });
            }
        });

        setSearchResults(matches);
    };

    const handleJumpToSearchMatch = (match) => {
        setActiveDocName(match.docName);
        setCurrentPage(match.page);
        setShowSearchPanel(false);
    };

    // Copy RAG snippet text helper
    const copySnippetToClipboard = () => {
        if (selectedCitation?.snippet) {
            navigator.clipboard.writeText(selectedCitation.snippet);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    return (
        <div className={`manual-viewer-root ${isFullscreen ? 'is-fullscreen' : ''}`} ref={viewerRef}>

            {/* 1. TOP TOOLBAR - Zoom, page navigation, fullscreen (Min 48px Touch Targets) */}
            <header className="viewer-toolbar">
                <div className="toolbar-left-group">
                    <BookOpen className="toolbar-icon" size={18} />
                    <select
                        className="document-selector-dropdown"
                        value={activeDocName}
                        onChange={handleDocChange}
                        aria-label="Select Technical Document"
                    >
                        {manualsList.map((m) => (
                            <option key={m.filename} value={m.filename}>
                                {m.filename.length > 25 ? `${m.filename.substring(0, 25)}...` : m.filename}
                            </option>
                        ))}
                    </select>
                    {isUsingFallback && (
                        <span className="offline-badge" title="No real manuals fetched, using cached fallback">
                            Offline Cache
                        </span>
                    )}
                </div>

                <div className="toolbar-center-navigation">
                    <button
                        className="toolbar-nav-btn"
                        onClick={handlePrevPage}
                        disabled={currentPage <= 1}
                        aria-label="Previous Page"
                    >
                        <ChevronLeft size={20} />
                    </button>

                    <div className="page-counter-input-row">
                        <span className="current-page-tag">Page {currentPage}</span>
                        <span className="divider-slash">/</span>
                        <span className="total-pages-tag">{totalPagesCount}</span>
                    </div>

                    <button
                        className="toolbar-nav-btn"
                        onClick={handleNextPage}
                        disabled={currentPage >= totalPagesCount}
                        aria-label="Next Page"
                    >
                        <ChevronRight size={20} />
                    </button>
                </div>

                <div className="toolbar-right-actions">
                    <button
                        className={`toolbar-btn search-toggle-btn ${showSearchPanel ? 'active' : ''}`}
                        onClick={() => setShowSearchPanel(!showSearchPanel)}
                        title="Search Manual"
                        aria-label="Search Manual"
                    >
                        <Search size={18} />
                    </button>

                    <div className="zoom-controls">
                        <button className="toolbar-btn" onClick={handleZoomOut} title="Zoom Out" aria-label="Zoom Out">
                            <ZoomOut size={16} />
                        </button>
                        <span className="zoom-percentage">{zoom}%</span>
                        <button className="toolbar-btn" onClick={handleZoomIn} title="Zoom In" aria-label="Zoom In">
                            <ZoomIn size={16} />
                        </button>
                    </div>

                    <button className="toolbar-btn fullscreen-btn" onClick={toggleFullscreen} title="Fullscreen View" aria-label="Toggle Fullscreen">
                        {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
                    </button>
                </div>
            </header>

            {/* 2. CONTEXTUAL SEARCH DRAWER */}
            {showSearchPanel && (
                <aside className="search-drawer-overlay">
                    <div className="search-drawer-header">
                        <h3>Search In Documents</h3>
                        <button className="close-drawer-btn" onClick={() => setShowSearchPanel(false)}>×</button>
                    </div>
                    <div className="search-drawer-body">
                        <div className="search-input-wrapper">
                            <Search size={16} className="search-pane-icon" />
                            <input
                                type="text"
                                placeholder="Search keywords (e.g. vibration, torque)..."
                                value={searchQuery}
                                onChange={handleSearch}
                                className="search-pane-input"
                                autoFocus
                            />
                        </div>

                        <div className="search-results-list">
                            {searchQuery && searchResults.length === 0 && (
                                <div className="search-no-results">No technical matches found.</div>
                            )}
                            {searchResults.map((match, idx) => (
                                <button
                                    key={idx}
                                    className="search-match-card"
                                    onClick={() => handleJumpToSearchMatch(match)}
                                >
                                    <span className="match-doc-name">{match.docName} (p. {match.page})</span>
                                    <span className="match-section-name">{match.section}</span>
                                    <span className="match-title-text">{match.title}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                </aside>
            )}

            {/* 3. CORE DOCUMENT AREA */}
            <main className="document-scroller-viewport">
                {/* Dynamic Zoom Wrapper */}
                <div
                    className="document-zoom-container"
                    style={{ transform: `scale(${zoom / 100})`, transformOrigin: 'top center' }}
                >
                    <div className="blueprint-paper-sheet">
                        {/* Header of technical documentation page */}
                        <div className="sheet-top-header">
                            <span className="sheet-doc-title">{activeManualRecord?.title}</span>
                            <span className="sheet-section-tag">{pageData.section}</span>
                        </div>

                        <div className="sheet-body-content">
                            {/* Left Column: Interactive Vector CAD Blueprint (Drawn dynamically via CSS) */}
                            <div className="blueprint-column-visual">
                                <div className="cad-grid-overlay"></div>
                                <div className={`vector-cad-drawing cad-${pageData.blueprintType}`}>
                                    {pageData.blueprintType === 'roller' && (
                                        <div className="vector-roller-graphic">
                                            <div className="outer-bearing"></div>
                                            <div className="inner-axis"></div>
                                            <div className="lube-injection-port"></div>
                                            <span className="cad-annotation label-x">D = 48.0 mm</span>
                                            <span className="cad-annotation label-y">Cylinder Shaft</span>
                                        </div>
                                    )}
                                    {pageData.blueprintType === 'cam' && (
                                        <div className="vector-cam-graphic">
                                            <div className="eccentric-lobe"></div>
                                            <div className="track-slider"></div>
                                            <div className="pressure-direction-arrow"></div>
                                            <span className="cad-annotation label-x">Cam Track</span>
                                            <span className="cad-annotation label-y">±0.05 mm Tol.</span>
                                        </div>
                                    )}
                                    {pageData.blueprintType === 'anchor' && (
                                        <div className="vector-anchor-graphic">
                                            <div className="ground-line"></div>
                                            <div className="anchor-stud"></div>
                                            <div className="expansion-shield"></div>
                                            <span className="cad-annotation label-x">M16 Bolt</span>
                                            <span className="cad-annotation label-y">C25 Concrete</span>
                                        </div>
                                    )}
                                    {pageData.blueprintType === 'motor' && (
                                        <div className="vector-motor-graphic">
                                            <div className="motor-housing"></div>
                                            <div className="cooling-fins"></div>
                                            <div className="drive-shaft-coupling"></div>
                                            <span className="cad-annotation label-x">Base Temp</span>
                                            <span className="cad-annotation label-y">60°C Max</span>
                                        </div>
                                    )}
                                    {pageData.blueprintType === 'default' && (
                                        <div className="vector-default-graphic">
                                            <FileText size={48} className="deco-file-icon" />
                                            <div className="generic-blueprint-block"></div>
                                            <span className="cad-annotation label-x">AROL Fleet</span>
                                        </div>
                                    )}
                                </div>
                                <div className="blueprint-engineering-footer">
                                    <span>SCALE: 1:5 • ALL DIMENSIONS IN MM • AROL DRAWING SYSTEM</span>
                                </div>
                            </div>

                            {/* Right Column: Detailed technical instruction sheet */}
                            <div className="blueprint-column-text">
                                <h1 className="instruction-headline">{pageData.title}</h1>

                                {/* Injected Snippet Highlighted Box */}
                                {pageData.isSnippetInjected ? (
                                    <div className="injected-rag-highlight-box">
                                        <span className="injected-badge">Real-Time Chroma DB Chunk</span>
                                        <p className="instruction-paragraph highlight-text">{pageData.text}</p>
                                    </div>
                                ) : (
                                    <p className="instruction-paragraph">{pageData.text}</p>
                                )}

                                <h2 className="specs-sub-header">
                                    <Sliders size={14} style={{ marginRight: '6px', color: 'var(--arol-blue)' }} />
                                    MECHANICAL PARAMETERS & LIMITS
                                </h2>

                                <table className="specs-rugged-table">
                                    <tbody>
                                        {pageData.specs.map((spec, i) => (
                                            <tr key={i}>
                                                <td className="spec-label-cell">{spec.label}</td>
                                                <td className="spec-value-cell">{spec.value}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Bottom corporate stamp */}
                        <div className="sheet-bottom-stamping">
                            <span>AROL S.P.A. • TECHNICAL SERVICE DEPARTMENT • STRICTLY CONFIDENTIAL</span>
                            <span>VER. 2026.07</span>
                        </div>
                    </div>
                </div>
            </main>

            {/* 4. FLOATING AI GROUNDED REFERENCE BANNER */}
            {selectedCitation && selectedCitation.snippet && (
                <footer className="ai-grounding-banner" aria-live="polite">
                    <div className="banner-badge-column">
                        <span className="banner-pill">AI GROUNDED REFERENCE</span>
                        <span className="banner-source-details">
                            {selectedCitation.docName} • Page {selectedCitation.page}
                        </span>
                    </div>

                    <div className="banner-snippet-body">
                        <p className="banner-snippet-text">
                            "{selectedCitation.snippet}"
                        </p>
                    </div>

                    <div className="banner-action-column">
                        <button
                            className={`copy-snippet-btn ${copied ? 'copied' : ''}`}
                            onClick={copySnippetToClipboard}
                            title="Copy snippet to clipboard"
                            aria-label="Copy snippet to clipboard"
                        >
                            {copied ? (
                                <>
                                    <Check size={16} />
                                    <span>Copied</span>
                                </>
                            ) : (
                                <>
                                    <Copy size={16} />
                                    <span>Copy</span>
                                </>
                            )}
                        </button>
                    </div>
                </footer>
            )}
        </div>
    );
}