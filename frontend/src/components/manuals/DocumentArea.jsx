import React, { useCallback, useState, useEffect } from 'react';
import { Document, Page } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

import 'react-pdf/dist/Page/TextLayer.css';

// pdf.js downloads the file with its own fetch, which by default sends cookies
// only to the same origin. The PDF is served by the backend (another origin),
// so the session cookie must be requested explicitly.
const PDF_OPTIONS = { withCredentials: true };
/**
 * Builds a Set of lowercase tokens from the RAG snippet.
 * Filters out short words (< 4 chars) to avoid false-positive highlights
 * on articles, prepositions and punctuation fragments.
 */
function buildSnippetTokens(snippet) {
    if (!snippet) return null;
    const tokens = snippet
        .toLowerCase()
        .replace(/[^\w\s]/g, ' ')   // strip punctuation
        .split(/\s+/)
        .filter(t => t.length >= 4);
    return tokens.length > 0 ? new Set(tokens) : null;
}

export default function DocumentArea({
    activePdfUrl,
    onDocumentLoadSuccess,
    currentPage,
    zoom,
    highlightSnippet = null,   // selectedCitation.snippet passed from ManualViewer
    searchQuery = '',
}) {
    // Pre-compute token set once per citation change (not on every span render)
    const snippetTokens = buildSnippetTokens(highlightSnippet);

    // Responsive width for mobile screens to prevent horizontal overflow
    const [pageWidth, setPageWidth] = useState(undefined);

    useEffect(() => {
        const handleResize = () => {
            if (window.innerWidth < 768) {
                // 40px accounts for the 20px padding on each side of the container
                setPageWidth(window.innerWidth - 40);
            } else {
                // On desktop, let the PDF render at its native width
                setPageWidth(undefined);
            }
        };

        handleResize();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    /**
     * customTextRenderer is called by react-pdf for every text span in the
     * text layer. It returns an HTML string: react-pdf injects it via
     * dangerouslySetInnerHTML, so <mark> tags are safe here.
     *
     * Strategy:
     * 1. AI RAG Snippets: Tokenise the AI snippet and highlight any span that contains
     *    at least one matching token. This handles the fact that react-pdf splits text 
     *    into small, variable-length items (a full-phrase match rarely aligns with spans).
     * 2. User Search Query: Dynamically find the exact searched word/substring within 
     *    the span and wrap it in a <mark> tag using a regular expression.
     */
    const customTextRenderer = useCallback(({ str }) => {
        if (!str.trim()) return str;

        let hasSnippetMatch = false;
        const strLower = str.toLowerCase();

        if (snippetTokens) {
            const strLowerTokens = strLower.replace(/[^\w\s]/g, ' ').split(/\s+/);
            hasSnippetMatch = strLowerTokens.some(word => word.length >= 4 && snippetTokens.has(word));
        }

        if (hasSnippetMatch) {
            return `<mark class="pdf-highlight">${str}</mark>`;
        }

        // Highlight search query accurately (multi-word support)
        if (searchQuery && searchQuery.trim().length > 1) {
            const queryTokens = searchQuery.trim().toLowerCase().split(/\s+/).filter(t => t.length > 2);
            if (queryTokens.length > 0) {
                const escapedTokens = queryTokens.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
                const regex = new RegExp(`(${escapedTokens.join('|')})`, 'gi');
                const newStr = str.replace(regex, '<mark class="pdf-highlight">$1</mark>');
                if (newStr !== str) {
                    return newStr;
                }
            }
        }

        return str;
    }, [snippetTokens, searchQuery]);

    return (
        <main className="document-scroller-viewport">
            {/* Dynamic Zoom Wrapper */}
            <div
                className="document-zoom-container"
                style={{
                    display: 'flex',
                    justifyContent: 'center',
                    padding: '20px'
                }}
            >
                {/* PDF Renderer */}
                {activePdfUrl ? (
                    <Document
                        file={activePdfUrl}
                        options={PDF_OPTIONS}
                        onLoadSuccess={onDocumentLoadSuccess}
                        loading={<div className="pdf-loading">PDF loading</div>}
                        error={<div className="pdf-error">Impossible PDF load<br /><small>{activePdfUrl}</small></div>}
                    >
                        <Page
                            pageNumber={currentPage}
                            scale={zoom / 100}
                            width={pageWidth}
                            renderTextLayer={true}
                            renderAnnotationLayer={true}
                            customTextRenderer={(snippetTokens || searchQuery) ? customTextRenderer : undefined}
                        />
                    </Document>
                ) : (
                    <div className="pdf-loading">Nessun manuale selezionato.</div>
                )}
            </div>
        </main>
    )
}