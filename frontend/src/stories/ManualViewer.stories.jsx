import React, { useState } from "react";
import DocumentArea from "../components/manuals/DocumentArea";
import AIReferenceBanner from "../components/manuals/AIReferenceBanner";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import "../styles/ManualViewer.css";
import "../styles/tokens.css";

// Local PDF served by Storybook from the /public folder — no backend required, no CORS issues.
// Contains AROL-flavoured text matching the highlight snippets below.
const TEST_PDF_URL = "/test-manual.pdf";

export default {
    title: "Manuals/PDFHighlight",
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: `
Tests the AI citation highlight feature in DocumentArea.
The customTextRenderer tokenises the highlightSnippet string and wraps
matching PDF text spans in mark.pdf-highlight, producing the amber underline.

**What to verify:**
- Words from the snippet appear highlighted in amber on the PDF page.
- Toggling the snippet ON/OFF shows/hides the marks.
- The AIReferenceBanner footer shows doc/page info and a working Copy button.
                `
            }
        }
    }
};

// Snippet whose tokens appear verbatim in test-manual.pdf
const MOCK_SNIPPET =
    "Routine inspection and lubrication idle rollers Euro VP capping head operating hours baseplate anchoring";

const MOCK_CITATION = {
    docName: "Manuale_Euro_VP_Manutenzione.pdf",
    page: 1,
    snippet: MOCK_SNIPPET,
};

// ---------------------------------------------------------------------------
// Story 1: No highlight - baseline render
// ---------------------------------------------------------------------------
export const NoHighlight = {
    name: "1. No highlight (baseline)",
    render: () => (
        <div style={{ height: "100vh" }}>
            <DocumentArea
                activePdfUrl={TEST_PDF_URL}
                onDocumentLoadSuccess={() => {}}
                currentPage={1}
                zoom={100}
                highlightSnippet={null}
            />
        </div>
    ),
};

// ---------------------------------------------------------------------------
// Story 2: Highlight active
// ---------------------------------------------------------------------------
export const WithHighlight = {
    name: "2. With highlight (amber mark on matching words)",
    render: () => (
        <div style={{ height: "100vh" }}>
            <DocumentArea
                activePdfUrl={TEST_PDF_URL}
                onDocumentLoadSuccess={() => {}}
                currentPage={1}
                zoom={100}
                highlightSnippet={MOCK_SNIPPET}
            />
        </div>
    ),
};

// ---------------------------------------------------------------------------
// Story 3: DocumentArea + AIReferenceBanner together
// ---------------------------------------------------------------------------
export const WithBannerAndHighlight = {
    name: "3. With AIReferenceBanner + highlight",
    render: () => {
        const [copied, setCopied] = useState(false);
        const handleCopy = () => {
            navigator.clipboard?.writeText(MOCK_CITATION.snippet);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        };

        return (
            <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
                <DocumentArea
                    activePdfUrl={TEST_PDF_URL}
                    onDocumentLoadSuccess={() => {}}
                    currentPage={1}
                    zoom={100}
                    highlightSnippet={MOCK_CITATION.snippet}
                />
                <AIReferenceBanner
                    selectedCitation={MOCK_CITATION}
                    copied={copied}
                    copySnippetToClipboard={handleCopy}
                />
            </div>
        );
    },
};

// ---------------------------------------------------------------------------
// Story 4: Interactive toggle
// ---------------------------------------------------------------------------
export const InteractiveToggle = {
    name: "4. Interactive - toggle highlight on/off",
    render: () => {
        const [active, setActive] = useState(true);

        return (
            <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "16px",
                        padding: "10px 16px",
                        background: "#1A252F",
                        color: "#fff",
                        fontFamily: "Inter, system-ui, sans-serif",
                        fontSize: "0.85rem",
                        flexShrink: 0,
                    }}
                >
                    <strong>PDF Highlight Test</strong>
                    <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                        <input
                            type="checkbox"
                            checked={active}
                            onChange={(e) => setActive(e.target.checked)}
                        />
                        Highlight snippet attivo
                    </label>
                    {active && (
                        <span style={{ opacity: 0.7, fontStyle: "italic" }}>
                            Snippet: "{MOCK_SNIPPET.slice(0, 55)}..."
                        </span>
                    )}
                </div>

                <DocumentArea
                    activePdfUrl={TEST_PDF_URL}
                    onDocumentLoadSuccess={() => {}}
                    currentPage={1}
                    zoom={120}
                    highlightSnippet={active ? MOCK_SNIPPET : null}
                />
            </div>
        );
    },
};
