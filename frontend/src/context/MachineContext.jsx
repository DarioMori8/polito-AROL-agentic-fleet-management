import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const MachineContext = createContext(null);

/**
 * MachineContext Provider.
 * Connects the frontend to the real FastAPI asset management endpoints:
 * - GET /v1/machines
 * - GET /v1/machines/{machine_id}
 * - GET /v1/machines/{machine_id}/manuals
 * Integrates sessionStorage caching for robust, offline-first industrial operations.
 */
export function MachineProvider({ children }) {
    const [fleet, setFleet] = useState([]);
    const [activeMachine, setActiveMachine] = useState(null);
    const [activeManuals, setActiveManuals] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Read the environment variable, fallback to default port 8000
    const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';

    // Load cached assets on mount to support instant app loading under flaky Wi-Fi
    useEffect(() => {
        try {
            const cachedFleet = sessionStorage.getItem('arol_cached_fleet');
            if (cachedFleet) {
                setFleet(JSON.parse(cachedFleet));
            }

            const cachedActiveMachine = sessionStorage.getItem('arol_active_machine');
            const cachedActiveManuals = sessionStorage.getItem('arol_active_manuals');
            if (cachedActiveMachine) {
                setActiveMachine(JSON.parse(cachedActiveMachine));
            }
            if (cachedActiveManuals) {
                setActiveManuals(JSON.parse(cachedActiveManuals));
            }
        } catch (e) {
            console.warn('Unable to load cached industrial assets from sessionStorage:', e);
        }
    }, []);

    /**
     * Fetches the entire machine park from the backend.
     * Overwrites local cache on success; falls back to cache on failure.
     */
    const fetchFleet = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(`${API_BASE_URL}/v1/machines`);
            if (!response.ok) {
                throw new Error(`HTTP Error: ${response.status}`);
            }
            const data = await response.json();
            setFleet(data);
            sessionStorage.setItem('arol_cached_fleet', JSON.stringify(data));
        } catch (err) {
            console.error('AROL Fleet Fetch Error:', err);
            const cachedFleet = sessionStorage.getItem('arol_cached_fleet');
            if (cachedFleet) {
                setFleet(JSON.parse(cachedFleet));
                setError('Working offline. Displaying cached fleet data.');
            } else {
                setError('Unable to fetch AROL machinery fleet. Check factory network.');
            }
        } finally {
            setLoading(false);
        }
    }, [API_BASE_URL]);

    /**
     * Resolves a machine ID after a QR Scan.
     * Downloads machine metadata and associated technical manuals in parallel.
     */
    const scanMachine = useCallback(async (id) => {
        if (!id) return;
        setLoading(true);
        setError(null);
        try {
            // Parallel fetch execution to optimize latency and bandwidth
            const [machineRes, manualsRes] = await Promise.all([
                fetch(`${API_BASE_URL}/v1/machines/${id}`),
                fetch(`${API_BASE_URL}/v1/machines/${id}/manuals`)
            ]);

            if (!machineRes.ok) {
                if (machineRes.status === 404) {
                    throw new Error(`Machine ID "${id}" is not registered in the AROL database.`);
                }
                throw new Error(`Failed to resolve machine. Status: ${machineRes.status}`);
            }

            const machineData = await machineRes.json();
            let manualsData = [];

            if (manualsRes.ok) {
                manualsData = await manualsRes.json();
            }

            // Update state and persistence layer
            setActiveMachine(machineData);
            setActiveManuals(manualsData);
            sessionStorage.setItem('arol_active_machine', JSON.stringify(machineData));
            sessionStorage.setItem('arol_active_manuals', JSON.stringify(manualsData));
        } catch (err) {
            console.error(`AROL QR Scan Error for ID ${id}:`, err);

            const cachedActiveMachine = sessionStorage.getItem('arol_active_machine');
            const cachedActiveManuals = sessionStorage.getItem('arol_active_manuals');

            if (cachedActiveMachine && JSON.parse(cachedActiveMachine).id === id) {
                setActiveMachine(JSON.parse(cachedActiveMachine));
                if (cachedActiveManuals) {
                    setActiveManuals(JSON.parse(cachedActiveManuals));
                }
                setError('Working offline. Displaying cached machine profile.');
            } else {
                setError(err.message || 'Connection failure. Unable to resolve scanned asset.');
            }
        } finally {
            setLoading(false);
        }
    }, [API_BASE_URL]);

    /**
     * Clears the current machine session (Logout / Reset Scan)
     */
    const clearMachine = useCallback(() => {
        setActiveMachine(null);
        setActiveManuals([]);
        sessionStorage.removeItem('arol_active_machine');
        sessionStorage.removeItem('arol_active_manuals');
    }, []);

    const isScanned = !!activeMachine;

    return (
        <MachineContext.Provider value={{
            fleet,
            activeMachine,
            activeManuals,
            loading,
            error,
            fetchFleet,
            scanMachine,
            clearMachine,
            isScanned
        }}>
            {children}
        </MachineContext.Provider>
    );
}

/**
 * Custom hook to consume the scanned machine context.
 */
export function useMachine() {
    const context = useContext(MachineContext);
    if (!context) {
        throw new Error('useMachine must be used within a MachineProvider');
    }
    return context;
}
