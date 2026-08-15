import React from 'react';
import { Document, Page } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

export default function DocumentArea({
    activePdfUrl,
    onDocumentLoadSuccess,
    currentPage,
    zoom,
}) {
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
                        />
                    </Document>
                ) : (
                    <div className="pdf-loading">Nessun manuale selezionato.</div>
                )}
            </div>
        </main>
    )
}