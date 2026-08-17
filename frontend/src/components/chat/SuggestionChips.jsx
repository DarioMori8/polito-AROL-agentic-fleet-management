import React from 'react';
import { Wrench, BookOpen, LineChart } from 'lucide-react';
import '../../styles/SuggestionChips.css';

/**
 * SuggestionChips Component (Rugged UI)
 * Renders the three primary quick action cards for the AROL conversational interface.
 * Directly mapped to the main active AI agents (Troubleshooting, Manuals, and IoT).
 */
export default function SuggestionChips({ onSuggestionClick }) {

    // Quick action templates matching the official UI sketch requirements
    const chips = [
        {
            id: 'troubleshoot',
            label: 'Guida alla Risoluzione Guasti',
            description: 'Start step-by-step interactive diagnostics',
            icon: <Wrench size={20} />,
            actionText: "Guida alla Risoluzione Guasti"
        },
        {
            id: 'manuals',
            label: 'Consulta Manuale Tecnico',
            description: 'Search PDF manuals and technical sheets',
            icon: <BookOpen size={20} />,
            actionText: "Consulta Manuale Tecnico"
        },
        {
            id: 'iot',
            label: 'Analisi Dati IoT in Tempo Reale',
            description: 'View real-time sensor telemetry and alarms',
            icon: <LineChart size={20} />,
            actionText: "Analisi Dati IoT in Tempo Reale"
        }
    ];

    const handleChipClick = (chip) => {
        if (onSuggestionClick) {
            // Passes both the structural ID and the direct text to trigger the chatbot flow
            onSuggestionClick(chip.id, chip.actionText);
        }
    };

    return (
        <div className="suggestion-chips-container">
            {chips.map((chip) => (
                <button
                    key={chip.id}
                    type="button"
                    className="suggestion-chip-btn"
                    onClick={() => handleChipClick(chip)}
                    aria-label={chip.label}
                    disabled={true}
                >
                    <span className="chip-icon">{chip.icon}</span>
                    <span className="chip-label">{chip.label}</span>
                </button>
            ))}
        </div>
    );
}