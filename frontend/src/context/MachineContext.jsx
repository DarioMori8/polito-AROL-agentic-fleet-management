import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const MachineContext = createContext(null);

/**
 * Robust helper to compare industrial machine IDs.
 * Handles single-digit string numbers ("2"), padded string numbers ("002"),
 * integers (2), and alphanumeric codes securely.
 */
export const isMatchingId = (idA, idB) => {
    if (idA === undefined || idA === null || idB === undefined || idB === null) return false;

    const strA = idA.toString().trim();
    const strB = idB.toString().trim();

    // Try numeric comparison first (handles "002" vs "2" or 2 vs "2")
    const numA = parseInt(strA, 10);
    const numB = parseInt(strB, 10);
    if (!isNaN(numA) && !isNaN(numB)) {
        return numA === numB;
    }

    // Case-insensitive string comparison for alphanumeric IDs
    return strA.toLowerCase() === strB.toLowerCase();
};

// Mock Fleet Dataset matching AROL Project Specifications
const MOCK_FLEET = [
    {
        id: "001",
        name: "AROL Capper #12",
        model: "Euro VP",
        serial_number: "AR-EVP-2026-098",
        status: "maintenance", // Renders warning state in UI
        location: "Bottling Line B (Canelli)"
    },
    {
        id: "002",
        name: "AROL Labeller #4",
        model: "Decolleté 3000",
        serial_number: "AR-DEC-2025-102",
        status: "online", // Renders success state in UI
        location: "Packaging Hall A"
    },
    {
        id: "003",
        name: "AROL Filler #9",
        model: "Isobaric Glass 40",
        serial_number: "AR-ISO-2024-441",
        status: "online",
        location: "Filling Dept 2"
    }
];

// Mock Manuals Dataset associated to machines
const MOCK_MANUALS = {
    "001": [
        { id: "man_1", machine_id: "001", title: "AROL Euro VP - Use & Maintenance Manual", filename: "Manuale_Euro_VP_Manutenzione.pdf", language: "EN", page_count: 80 },
        { id: "man_2", machine_id: "001", title: "AROL Structural Anchoring Specs", filename: "Specifiche_Ancoraggio_AROL.pdf", language: "EN", page_count: 30 }
    ],
    "002": [
        { id: "man_3", machine_id: "002", title: "AROL Mechanical Torque Standards", filename: "Specifiche_Serraggio_Q2.pdf", language: "EN", page_count: 18 }
    ]
};

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

    // Read the environment variables
    const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';
    const USE_MOCK = import.meta.env?.VITE_USE_MOCK === 'true';

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

        if (USE_MOCK) {
            // Simulate minor network delay for realistic loader rendering
            await new Promise(resolve => setTimeout(resolve, 600));
            setFleet(MOCK_FLEET);
            setLoading(false);
            return;
        }

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
    }, [API_BASE_URL, USE_MOCK]);

    /**
     * Resolves a machine ID after a QR Scan.
     * Downloads machine metadata and associated technical manuals in parallel.
     */
    const scanMachine = useCallback(async (id) => {
        if (!id) return;
        setLoading(true);
        setError(null);

        // UX OPTIMIZATION: Set active machine IMMEDIATELY if already loaded in fleet state
        const localMatch = fleet.find(m => isMatchingId(m.id, id));
        if (localMatch) {
            setActiveMachine(localMatch);
        }

        // Mock mode
        if (USE_MOCK) {
            await new Promise(resolve => setTimeout(resolve, 500));
            const machine = MOCK_FLEET.find(m => isMatchingId(m.id, id));
            if (!machine) {
                setError(`Machine ID "${id}" is not registered in the AROL mock fleet.`);
                setLoading(false);
                return;
            }
            const manuals = MOCK_MANUALS[machine.id] || [];

            setActiveMachine(machine);
            setActiveManuals(manuals);
            sessionStorage.setItem('arol_active_machine', JSON.stringify(machine));
            sessionStorage.setItem('arol_active_manuals', JSON.stringify(manuals));
            setLoading(false);
            return;
        }

        // Real-world scenario - Fetch from API
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

            // Only fall back to cache if the cached machine actually matches the requested ID
            if (cachedActiveMachine && isMatchingId(JSON.parse(cachedActiveMachine).id, id)) {
                setActiveMachine(JSON.parse(cachedActiveMachine));
                if (cachedActiveManuals) {
                    setActiveManuals(JSON.parse(cachedActiveManuals));
                }
                setError('Working offline. Displaying cached machine profile.');
            } else {
                // Fallback: If cache doesn't match but we have the fleet array match, preserve the localMatch
                if (localMatch) {
                    setActiveMachine(localMatch);
                    setError('Offline. Loaded machine details from active fleet memory.');
                } else {
                    setError(err.message || 'Connection failure. Unable to resolve scanned asset.');
                }
            }
        } finally {
            setLoading(false);
        }
    }, [API_BASE_URL, USE_MOCK, fleet]);

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
