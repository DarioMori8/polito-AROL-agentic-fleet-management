import React, { useCallback } from 'react';
import { Document, Page } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

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
}) {
    // Pre-compute token set once per citation change (not on every span render)
    const snippetTokens = buildSnippetTokens(highlightSnippet);

    /**
     * customTextRenderer is called by react-pdf for every text span in the
     * text layer. It returns an HTML string: react-pdf injects it via
     * dangerouslySetInnerHTML, so <mark> tags are safe here.
     *
     * Strategy: tokenise the snippet and highlight any span that contains
     * at least one matching token. This handles the fact that react-pdf
     * splits text into small, variable-length items — a full-phrase match
     * would almost never align with the exact span boundaries.
     */
    const customTextRenderer = useCallback(({ str }) => {
        if (!snippetTokens || !str.trim()) return str;

        const strLower = str.toLowerCase().replace(/[^\w\s]/g, ' ');
        const hasMatch = strLower
            .split(/\s+/)
            .some(word => word.length >= 4 && snippetTokens.has(word));

        return hasMatch
            ? `<mark class="pdf-highlight">${str}</mark>`
            : str;
    }, [snippetTokens]);

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
                        onLoadSuccess={onDocumentLoadSuccess}
                        loading={<div className="pdf-loading">Caricamento PDF in corso...</div>}
                        error={<div className="pdf-error">Impossibile caricare il file PDF.<br /><small>{activePdfUrl}</small></div>}
                    >
                        <Page
                            pageNumber={currentPage}
                            scale={zoom / 100}
                            renderTextLayer={true}
                            renderAnnotationLayer={true}
                            customTextRenderer={snippetTokens ? customTextRenderer : undefined}
                        />
                    </Document>
                ) : (
                    <div className="pdf-loading">Nessun manuale selezionato.</div>
                )}
            </div>
        </main>
    )
}