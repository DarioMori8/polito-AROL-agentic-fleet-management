import React from 'react';
import { BookOpen, ChevronLeft, ChevronRight, Search, ZoomOut, ZoomIn, Minimize2, Maximize2 } from 'lucide-react';
import Button from '@/components/ui/Button';

export default function TopToolbar({
    activeDocName,
    activeManuals,
    handleDocChange,
    currentPage,
    totalPagesCount,
    handlePrevPage,
    handleNextPage,
    showSearchPanel,
    setShowSearchPanel,
    zoom,
    handleZoomOut,
    handleZoomIn,
    isFullscreen,
    toggleFullscreen,
}) {
    return (
        <header className="viewer-toolbar">
            <div className="toolbar-left-group">
                <BookOpen className="toolbar-icon" size={18} />
                <select
                    className="document-selector-dropdown"
                    value={activeDocName}
                    onChange={handleDocChange}
                    aria-label="Select Technical Document"
                >
                    {activeManuals.map((m) => (
                        <option key={m.filename} value={m.filename}>
                            {m.filename.length > 25 ? `${m.filename.substring(0, 25)}...` : m.filename}
                        </option>
                    ))}
                </select>
            </div>

            <div className="toolbar-center-navigation">
                <Button
                    variant="ghost"
                    className="toolbar-nav-btn"
                    onClick={handlePrevPage}
                    disabled={currentPage <= 1}
                    aria-label="Previous Page"
                >
                    <ChevronLeft size={20} />
                </Button>

                <div className="page-counter-input-row">
                    <span className="current-page-tag">Page {currentPage}</span>
                    <span className="divider-slash">/</span>
                    <span className="total-pages-tag">{totalPagesCount}</span>
                </div>

                <Button
                    variant="ghost"
                    className="toolbar-nav-btn"
                    onClick={handleNextPage}
                    disabled={currentPage >= totalPagesCount}
                    aria-label="Next Page"
                >
                    <ChevronRight size={20} />
                </Button>
            </div>

            <div className="toolbar-right-actions">
                <Button
                    variant="ghost"
                    className={`toolbar-btn search-toggle-btn ${showSearchPanel ? 'active' : ''}`}
                    onClick={() => setShowSearchPanel(!showSearchPanel)}
                    title="Search Manual"
                    aria-label="Search Manual"
                >
                    <Search size={18} />
                </Button>

                <div className="zoom-controls">
                    <Button variant="ghost" className="toolbar-btn" onClick={handleZoomOut} title="Zoom Out" aria-label="Zoom Out">
                        <ZoomOut size={16} />
                    </Button>
                    <span className="zoom-percentage">{zoom}%</span>
                    <Button variant="ghost" className="toolbar-btn" onClick={handleZoomIn} title="Zoom In" aria-label="Zoom In">
                        <ZoomIn size={16} />
                    </Button>
                </div>

                <Button variant="ghost" className="toolbar-btn fullscreen-btn" onClick={toggleFullscreen} title="Fullscreen View" aria-label="Toggle Fullscreen">
                    {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
                </Button>
            </div>
        </header>
    )
}