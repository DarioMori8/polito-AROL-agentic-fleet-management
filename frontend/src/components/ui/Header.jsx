import React from 'react';
import { ArrowLeft, User } from 'lucide-react';
import '../../styles/Header.css';

/**
 * Reusable app-wide Header shell.
 * Renders a consistent back button (left), an operator profile icon (right),
 * and accepts arbitrary children for the centre content slot.
 *
 * Props:
 *  - onBackClick {Function} — called when the back arrow is pressed
 *  - children    {ReactNode} — centre content (e.g. machine info, page title)
 */
export default function Header({ onBackClick, children }) {
    return (
        <header className="chat-header">
            <button
                className="header-back-btn"
                onClick={onBackClick}
                aria-label="Go back"
            >
                <ArrowLeft size={24} />
            </button>

            <div style={{ flex: 1 }}>
                {children}
            </div>

            <div className="header-operator-profile" title="Operator Profile">
                <User size={20} />
            </div>
        </header>
    );
}