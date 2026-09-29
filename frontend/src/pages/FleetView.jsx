import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { Cpu, ShieldAlert, CheckCircle2, Search, RefreshCw, AlertTriangle, LogOut, User } from 'lucide-react';
import { useMachine } from '../context/MachineContext';
import { useAuth } from '../context/AuthContext';
import '../styles/FleetView.css';

/**
 * FleetView Component
 * Renders the dashboard showing all available machinery in the industrial fleet.
 * Allows searching, filtering, and clicking a machine card to simulate a QR scan.
 */
export default function FleetView() {
    const navigate = useNavigate();
    const { fleet, loading, error, fetchFleet } = useMachine();
    const { user, logout } = useAuth();
    const [searchQuery, setSearchQuery] = useState('');
    const [activeFilter, setActiveFilter] = useState('all');

    const handleLogout = async () => {
        await logout();
        navigate('/login', { replace: true });
    };

    // Trigger fleet load from server on mount
    useEffect(() => {
        fetchFleet();
    }, [fetchFleet]);

    // Status mappings: 'online' -> Operating, others -> In Alarm / Under Maintenance
    const filteredFleet = fleet.filter(m => {
        const nameToSearch = m.name || m.model_id || m.id.toString();
        const matchesSearch = nameToSearch.toLowerCase().includes(searchQuery.toLowerCase()) || m.id.toString().toLowerCase().includes(searchQuery.toLowerCase());
        const mStatus = m.status || 'online'; // Fallback if backend has no status
        
        if (activeFilter === 'all') return matchesSearch;
        if (activeFilter === 'ok') return matchesSearch && (mStatus === 'online');
        if (activeFilter === 'alarm') return matchesSearch && (mStatus !== 'online');
        return matchesSearch;
    });

    const handleMachineClick = (id) => {
        // Navigate dynamically to the scanned machine landing resolver
        navigate(`/machine/${id}`);
    };

    return (
        <div className="fleet-view-container">
            <header className="fleet-header">
                <div className="fleet-brand">AROL Group</div>
                <h1 className="fleet-title">Flotta Macchinari</h1>
                <p className="fleet-subtitle">Digital Fleet Portal &amp; Asset Control</p>

                <div className="fleet-header-actions">
                    {/* User session pill */}
                    {user && (
                        <div className="fleet-user-pill">
                            <User size={13} />
                            <span>{user.first_name || user.email}</span>
                        </div>
                    )}

                    {/* Dynamic Sync Trigger */}
                    <button className="sync-fleet-btn" onClick={fetchFleet} disabled={loading} style={{ touchAction: 'manipulation' }}>
                        <RefreshCw size={14} className={loading ? 'spinning-icon' : ''} />
                        <span>Sincronizza</span>
                    </button>

                    {/* Logout */}
                    <button className="logout-btn" onClick={handleLogout} style={{ touchAction: 'manipulation' }}>
                        <LogOut size={14} />
                        <span>Esci</span>
                    </button>
                </div>
            </header>

            <main className="fleet-main">
                {/* Connection Failure Toast Alert */}
                {error && (
                    <div className="connection-error-banner">
                        <AlertTriangle size={16} />
                        <span>{error}</span>
                    </div>
                )}


                {/* Search Input Bar (Rugged Touch Target) */}
                <div className="search-bar-rugged">
                    <Search className="search-icon" size={18} />
                    <input
                        type="text"
                        placeholder="Cerca per macchinario o ID..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="search-input-rugged"
                    />
                </div>

                {/* Filter Selection Row */}
                <div className="filter-chips-row">
                    <button className={`filter-chip ${activeFilter === 'all' ? 'active' : ''}`} onClick={() => setActiveFilter('all')}>
                        Tutti ({fleet.length})
                    </button>
                    <button className={`filter-chip ${activeFilter === 'ok' ? 'active' : ''}`} onClick={() => setActiveFilter('ok')}>
                        Operativi ({fleet.filter(m => (m.status || 'online') === 'online').length})
                    </button>
                    <button className={`filter-chip ${activeFilter === 'alarm' ? 'active' : ''}`} onClick={() => setActiveFilter('alarm')}>
                        In Errore ({fleet.filter(m => (m.status || 'online') !== 'online').length})
                    </button>
                </div>

                {loading && fleet.length === 0 ? (
                    <div className="fleet-loading-view">
                        <RefreshCw size={36} className="spinning-icon" />
                        <p>Interrogazione database macchinari in corso...</p>
                    </div>
                ) : (
                    <div className="fleet-grid"> {/* Fleet Card Grid */}
                        {filteredFleet.map((machine) => (
                            <div
                                key={machine.id}
                                className={`machine-card-rugged ${(machine.status || 'online') !== 'online' ? 'border-alarm' : ''}`}
                                onClick={() => handleMachineClick(machine.id)}
                                style={{ touchAction: 'manipulation' }}
                            >
                                <div className="card-hardware-icon-wrapper">
                                    <Cpu size={24} />
                                </div>

                                <div className="card-info">
                                    <h3 className="card-machine-name">{machine.name || machine.model_id || 'AROL Machine'}</h3>
                                    <span className="card-machine-id">ID: {machine.id} ({machine.model || machine.model_id || 'Standard'})</span>
                                    <span className="card-machine-dept">S/N: {machine.serial_number || 'N/D'} • {machine.location || machine.plant_location || 'Sconosciuta'}</span>

                                    <div className="card-status-row">
                                        {(machine.status || 'online') !== 'online' ? (
                                            <span className="card-badge badge-error">
                                                <ShieldAlert size={12} style={{ marginRight: '4px' }} />
                                                Stato: {(machine.status || 'online') === 'maintenance' ? 'Manutenzione' : 'Offline'}
                                            </span>
                                        ) : (
                                            <span className="card-badge badge-success">
                                                <CheckCircle2 size={12} style={{ marginRight: '4px' }} />
                                                Stato: Operativo
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </main>

            <footer className="fleet-footer">
                <p>© 2026 AROL Group S.p.A. • Canelli (AT)</p>
                <span className="footer-system-tag">Smart Factory Agentic Fleet</span>
            </footer>
        </div>
    );
}