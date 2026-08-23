import React, { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { useMachine } from '@/context/MachineContext';
import { MOCK_MANUALS_DATABASE } from '@/assets/mocks/MOCK_MANUALS_DATABASE';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import '@/styles/ManualViewer.css';
import TopToolbar from './TopToolbar';
import SearchDrawer from './SearchDrawer';
import DocumentArea from './DocumentArea';
import AIReferenceBanner from './AIReferenceBanner';

// Configure PDF.js worker via Vite's ?url import.
// Using ?url ensures Vite includes the file as a proper JS asset and serves it
// with Content-Type: application/javascript — avoiding the MIME type error that
// occurs when the worker is loaded as a generic binary (application/octet-stream).
pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;

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
    const [pdfTextContent, setPdfTextContent] = useState([]);
    const [isExtractingText, setIsExtractingText] = useState(false);

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

    // Clear extracted text when changing document
    useEffect(() => {
        setPdfTextContent([]);
    }, [activeDocName]);

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

    // Retrieve current active manual details
    const activeManualRecord = activeManuals.find(m => m.filename === activeDocName);
    const totalPagesCount = numPages ?? (activeManualRecord ? activeManualRecord.page_count : 100);

    // Build the absolute PDF URL.
    // The backend returns a relative path (e.g. "/static/manuals/file.pdf").
    // We must prepend the API origin so react-pdf fetches from the backend,
    // not from the Vite dev server (different port → wrong origin → Invalid PDF).
    const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';
    const activePdfUrl = activeManualRecord?.url
        ? (activeManualRecord.url.startsWith('http') || activeManualRecord.url.startsWith('blob:') ? activeManualRecord.url : `${API_BASE_URL}${activeManualRecord.url}`)
        : null;

    // Callback to extract text from each page of PDF when a document is loaded
    const onDocumentLoadSuccess = async (pdf) => {
        setNumPages(pdf.numPages);
        // Reset to page 1 only if current page exceeds the real page count
        if (currentPage > pdf.numPages) setCurrentPage(1);

        setIsExtractingText(true);
        const extractedText = [];
        try {
            for (let i = 1; i <= pdf.numPages; i++) {
                const page = await pdf.getPage(i);
                const textContent = await page.getTextContent();
                const pageText = textContent.items.map(item => item.str).join(' ');
                extractedText.push({ page: i, text: pageText });
            }
            setPdfTextContent(extractedText);
        } catch (error) {
            console.error("Error extracting PDF text for search", error);
        } finally {
            setIsExtractingText(false);
        }
    };

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

    // Document Navigation - Specific Page
    const handlePageChange = (newPage) => {
        if (newPage >= 1 && newPage <= totalPagesCount) {
            setCurrentPage(newPage);
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

    // Document Navigation - Client-side full-text search across current document and titles.
    useEffect(() => {
        if (!searchQuery.trim()) {
            setSearchResults([]);
            return;
        }

        const lowerQuery = searchQuery.toLowerCase();
        const matches = [];

        // 1. Search across all available manuals by title and filename
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

        // 2. Search inside the CURRENT document text
        pdfTextContent.forEach((item) => {
            const textLower = item.text.toLowerCase();
            let currentIndex = 0;
            while (currentIndex < textLower.length) {
                const index = textLower.indexOf(lowerQuery, currentIndex);
                if (index === -1) break;

                const start = Math.max(0, index - 40);
                const end = Math.min(item.text.length, index + 40);
                let snippet = item.text.substring(start, end);
                if (start > 0) snippet = '...' + snippet;
                if (end < item.text.length) snippet = snippet + '...';

                matches.push({
                    docName: activeDocName,
                    page: item.page,
                    section: `Page ${item.page}`,
                    title: snippet
                });

                currentIndex = index + lowerQuery.length;
            }
        });

        setSearchResults(matches);
    }, [searchQuery, pdfTextContent, activeManuals, activeDocName]);

    const handleSearch = (e) => {
        setSearchQuery(e.target.value);
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
                handlePageChange={handlePageChange}
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
                isExtractingText={isExtractingText}
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
                searchQuery={searchQuery}
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
