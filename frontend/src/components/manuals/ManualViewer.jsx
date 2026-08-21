import React, { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { useMachine } from '@/context/MachineContext';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import '@/styles/ManualViewer.css';
import TopToolbar from './TopToolbar';
import SearchDrawer from './SearchDrawer';
import DocumentArea from './DocumentArea';
import AIReferenceBanner from './AIReferenceBanner';

// Configure PDF.js worker — use local bundle via Vite's import.meta.url
// to avoid version mismatches with CDN-served workers.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url
).toString();

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

    // PDF page count from react-pdf (overrides metadata count when available)
    const [numPages, setNumPages] = useState(null);

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

    // Settle on an initial active document when manuals are retrieved or modified
    useEffect(() => {
        if (activeManuals.length > 0) {
            // If our current doc is not in the list, set the first available manual
            const docExists = activeManuals.some(m => m.filename === activeDocName);
            if (!docExists) {
                setActiveDocName(activeManuals[0].filename);
                setCurrentPage(1);
            }
        }
    }, [activeManuals, activeDocName]);

    // Settle on the active doc based on the selected citation
    useEffect(() => {
        if (selectedCitation && selectedCitation.docName) {
            const matchExists = activeManuals.some(m => m.filename === selectedCitation.docName);
            if (matchExists) {
                setActiveDocName(selectedCitation.docName);
                setCurrentPage(selectedCitation.page || 1);
            } else {
                // Safe check for offline match
                if (MOCK_MANUALS_DATABASE[selectedCitation.docName]) {
                    setActiveDocName(selectedCitation.docName);
                    setCurrentPage(selectedCitation.page || 1);
                }
            }
        }
    }, [selectedCitation, activeManuals]);

    // 0. Retrieve current active manual details
    const activeManualRecord = activeManuals.find(m => m.filename === activeDocName);
    const totalPagesCount = numPages ?? (activeManualRecord ? activeManualRecord.page_count : 100);

    // 1. Build the absolute PDF URL.
    // The backend returns a relative path (e.g. "/static/manuals/file.pdf").
    // We must prepend the API origin so react-pdf fetches from the backend,
    // not from the Vite dev server (different port → wrong origin → Invalid PDF).
    const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';
    const activePdfUrl = activeManualRecord?.url
        ? `${API_BASE_URL}${activeManualRecord.url}`
        : null;

    const onDocumentLoadSuccess = ({ numPages }) => {
        setNumPages(numPages);
        // Reset to page 1 only if current page exceeds the real page count
        if (currentPage > numPages) setCurrentPage(1);
    };

    // 2. Build the viewer card data: prioritize live RAG citation snippets, then show a generic placeholder
    const buildPageCard = () => {
        // 1. If the user navigated to this exact page via an AI citation and we have a real RAG snippet, show it
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

        // 2. Generic placeholder for pages without a live RAG snippet
        const machineLabel = activeMachine ? `${activeMachine.name || activeMachine.id}` : 'Unknown Machine';
        return {
            section: 'Technical Instruction Sheet',
            title: 'AROL SYSTEM RUNTIME DOCUMENTATION',
            text: `This technical documentation segment is dynamically cataloged on the server. You are viewing page ${currentPage} of ${activeDocName}. Please consult the RAG chatbot to query specific troubleshooting procedures or maintenance thresholds from this manual.`,
            specs: [
                { label: 'Document Name', value: activeDocName },
                { label: 'Active Page', value: `${currentPage} / ${totalPagesCount}` },
                { label: 'Active Machine', value: machineLabel }
            ],
            blueprintType: 'default'
        };
    };

    const pageCard = buildPageCard();

    // DOCUMENT NAVIGATION HANDLERS //
    // Document Navigation - Next Page
    const handleNextPage = () => {
        if (currentPage < totalPagesCount) {
            setCurrentPage((prev) => prev + 1);
        }
    };

    // Document Navigation - Previous Page
    const handlePrevPage = () => {
        if (currentPage > 1) {
            setCurrentPage((prev) => prev - 1);
        }
    };

    // Document Navigation - Document Change
    const handleDocChange = (e) => {
        const docName = e.target.value;
        setActiveDocName(docName);
        setCurrentPage(1);
    };

    // Document Navigation - Zoom Operations
    const handleZoomIn = () => setZoom((prev) => Math.min(prev + 10, 150));
    const handleZoomOut = () => setZoom((prev) => Math.max(prev - 10, 70));

    // Document Navigation - Fullscreen toggle
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

    // Document Navigation - Listen for native escape keys to reset fullscreen state
    useEffect(() => {
        const handleFullscreenChange = () => {
            setIsFullscreen(!!document.fullscreenElement);
        };
        document.addEventListener('fullscreenchange', handleFullscreenChange);
        return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
    }, []);

    // Document Navigation - Client-side index search (title/filename only).
    // NOTE: Full-text page search requires a backend RAG query to ChromaDB — not available client-side.
    const handleSearch = (e) => {
        const query = e.target.value;
        setSearchQuery(query);
        if (!query.trim()) {
            setSearchResults([]);
            return;
        }

        const lowerQuery = query.toLowerCase();
        const matches = [];

        // Search across all available manuals by title and filename
        activeManuals.forEach(m => {
            const titleMatch = m.title?.toLowerCase().includes(lowerQuery);
            const filenameMatch = m.filename?.toLowerCase().includes(lowerQuery);
            if (titleMatch || filenameMatch) {
                matches.push({
                    docName: m.filename,
                    page: 1,
                    title: m.title || m.filename,
                    section: 'Document Cover'
                });
            }
        });

        setSearchResults(matches);
    };

    // Document Navigation - Handle user clicks on search results
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

    // Manual Viewer Component UI
    return (
        <div className={`manual-viewer-root ${isFullscreen ? 'is-fullscreen' : ''}`} ref={viewerRef}>

            {/* 1. TOP TOOLBAR - Zoom, page navigation, fullscreen (Min 48px Touch Targets) */}
            <TopToolbar
                activeDocName={activeDocName}
                activeManuals={activeManuals}
                handleDocChange={handleDocChange}
                currentPage={currentPage}
                totalPagesCount={totalPagesCount}
                handlePrevPage={handlePrevPage}
                handleNextPage={handleNextPage}
                showSearchPanel={showSearchPanel}
                setShowSearchPanel={setShowSearchPanel}
                zoom={zoom}
                handleZoomOut={handleZoomOut}
                handleZoomIn={handleZoomIn}
                isFullscreen={isFullscreen}
                toggleFullscreen={toggleFullscreen}
            />

            {/* 2. CONTEXTUAL SEARCH DRAWER */}
            <SearchDrawer
                showSearchPanel={showSearchPanel}
                setShowSearchPanel={setShowSearchPanel}
                searchQuery={searchQuery}
                handleSearch={handleSearch}
                searchResults={searchResults}
                handleJumpToSearchMatch={handleJumpToSearchMatch}
            />


            {/* 3. CORE DOCUMENT AREA */}
            <DocumentArea
                activePdfUrl={activePdfUrl}
                onDocumentLoadSuccess={onDocumentLoadSuccess}
                currentPage={currentPage}
                zoom={zoom}
                highlightSnippet={
                    selectedCitation?.docName === activeDocName &&
                        selectedCitation?.page === currentPage
                        ? selectedCitation.snippet
                        : null
                }
            />

            {/* 4. FLOATING AI GROUNDED REFERENCE BANNER */}
            {/* <AIReferenceBanner
                selectedCitation={selectedCitation}
                copied={copied}
                copySnippetToClipboard={copySnippetToClipboard}
            /> */}
        </div>
    );
}