import React, { createContext, useContext, useState, useEffect } from 'react';

const MachineContext = createContext();

/**
 * Mock database representing the AROL machinery fleet.
 * Acts as a fallback/mock data source before connecting to the FastAPI backend.
 * TO BE DELETED WHEN FASTAPI AND REAL DB IS READY
 */
const MOCK_MACHINES_DB = {
    '001': {
        id: '001',
        name: 'AROL Capper #12',
        department: 'Reparto Imbottigliamento',
        status: 'In Allarme', // Can be: 'Operativo', 'In Allarme', 'In Manutenzione'
        serialNumber: 'AR-CAP12-2026',
        installationDate: '2023-05-14',
        lastMaintenance: '2026-06-10',
        modelType: 'Euro VP'
    },
    '002': {
        id: '002',
        name: 'AROL Labeller #4',
        department: 'Reparto Etichettatura',
        status: 'Operativo',
        serialNumber: 'AR-LAB04-2025',
        installationDate: '2024-02-18',
        lastMaintenance: '2026-05-22',
        modelType: 'Deco'
    },
    '003': {
        id: '003',
        name: 'AROL Filler #9',
        department: 'Reparto Riempimento',
        status: 'Operativo',
        serialNumber: 'AR-FIL09-2024',
        installationDate: '2022-11-05',
        lastMaintenance: '2026-07-01',
        modelType: 'Iso VP'
    }
};

/**
 * MachineProvider manages the global state of the scanned machine.
 * It integrates PWA session-persistence to keep the context secure against network drops.
 */
export function MachineProvider({ children }) {
    const [activeMachine, setActiveMachine] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Restore state from sessionStorage (resilience for rugged devices on browser reload)
    useEffect(() => {
        const savedMachineId = sessionStorage.getItem('arol_active_machine_id');
        if (savedMachineId && MOCK_MACHINES_DB[savedMachineId]) {
            setActiveMachine(MOCK_MACHINES_DB[savedMachineId]);
        }
    }, []);

    /**
     * Executes QR scan resolution.
     * Feeds machine context into the ecosystem.
     * @param {string} machineId - Extracted ID from QR scan route (/machine/:id)
     */
    const scanMachine = async (machineId) => {
        setLoading(true);
        setError(null);

        try {
            // TODO: REPLACE WITH REAL API CALL
            // Simulate API response delay (DoD Phase 0/1 compliance)
            await new Promise((resolve) => setTimeout(resolve, 600));

            const machineData = MOCK_MACHINES_DB[machineId];
            if (machineData) {
                setActiveMachine(machineData);
                sessionStorage.setItem('arol_active_machine_id', machineId);
            } else {
                throw new Error(`Machine with ID ${machineId} not found in AROL Fleet.`);
            }
        } catch (err) {
            setError(err.message || 'Error scanning machine.');
            setActiveMachine(null);
            sessionStorage.removeItem('arol_active_machine_id');
        } finally {
            setLoading(false);
        }
    };

    /**
     * Clears the current machine context, resetting the app to fleet view or landing scanner.
     */
    const clearMachine = () => {
        setActiveMachine(null);
        setError(null);
        sessionStorage.removeItem('arol_active_machine_id');
    };

    /**
     * Updates the status of the current machine dynamically.
     * Highly useful for real-time IoT events and alarms fetched via SSE/WebSockets.
     * @param {string} newStatus - 'Operativo', 'In Allarme', or 'In Manutenzione'
     */
    const updateMachineStatus = (newStatus) => {
        setActiveMachine((prev) => {
            if (!prev) return null;
            return {
                ...prev,
                status: newStatus
            };
        });
    };

    return (
        <MachineContext.Provider
            value={{
                activeMachine,
                loading,
                error,
                scanMachine,
                clearMachine,
                updateMachineStatus,
                isScanned: !!activeMachine
            }}
        >
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
