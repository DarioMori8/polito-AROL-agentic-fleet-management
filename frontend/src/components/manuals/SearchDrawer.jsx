import React from 'react';
import { Search } from 'lucide-react';

export default function SearchDrawer({
    showSearchPanel,
    setShowSearchPanel,
    searchQuery,
    handleSearch,
    searchResults,
    handleJumpToSearchMatch,
}) {
    return (<>
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
        )}</>)
}