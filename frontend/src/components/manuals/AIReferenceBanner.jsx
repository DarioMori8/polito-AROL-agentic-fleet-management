import React from 'react';
import { Copy, Check } from 'lucide-react';

export default function AIReferenceBanner({
    selectedCitation,
    copied,
    copySnippetToClipboard,
}) {
    return (
        <>
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
        </>
    )
}