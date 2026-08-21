import React from 'react';
import { Cpu, ShieldAlert, AlertTriangle, CheckCircle2 } from 'lucide-react';
import Header from '../ui/Header';

const renderStatusBadge = (status) => {
    const sanitizedStatus = status ? status.toLowerCase() : '';
    if (sanitizedStatus.includes('allarme') || sanitizedStatus.includes('errore')) {
        return (
            <span className="status-indicator badge-error">
                <ShieldAlert size={14} className="status-icon" />
                {status}
            </span>
        );
    }
    if (sanitizedStatus.includes('manutenzione')) {
        return (
            <span className="status-indicator badge-warning">
                <AlertTriangle size={14} className="status-icon" />
                {status}
            </span>
        );
    }
    return (
        <span className="status-indicator badge-success">
            <CheckCircle2 size={14} className="status-icon" />
            {status || 'Operativo'}
        </span>
    );
};

export default function ChatWindowHeader({ activeMachine, onBackClick }) {
    return (
        <Header onBackClick={onBackClick}>
            <div className="header-machine-info">
                <div className="machine-title-row">
                    <Cpu size={18} className="machine-hardware-icon" />
                    <h1 className="machine-name">{activeMachine?.name || 'Macchinario AROL'}</h1>
                </div>
                <div className="machine-meta-row">
                    <span className="machine-id">ID: {activeMachine?.id || '---'}</span>
                    {activeMachine?.status && renderStatusBadge(activeMachine.status)}
                </div>
            </div>
        </Header>
    );
}