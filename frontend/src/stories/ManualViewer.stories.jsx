import React from 'react';
import ManualViewer from '../components/manuals/ManualViewer';
import { MachineContext } from '@/context/MachineContext';

export default {
    title: 'Components/Manuals/ManualViewer',
    component: ManualViewer,
    parameters: {
        layout: 'fullscreen',
    },
};

const MockMachineProvider = ({ children }) => {
    // Mock the context value that ManualViewer expects
    const mockContextValue = {
        activeMachine: { id: 'MOCK-001', name: 'Test Industrial Machine' },
        activeManuals: [
            {
                filename: 'test-manual.pdf',
                title: 'Storybook Test Manual',
                // Assuming Storybook serves the public directory at the root
                url: window.location.origin + '/test-manual.pdf',
                page_count: 10
            }
        ],
    };

    return (
        <MachineContext.Provider value={mockContextValue}>
            {children}
        </MachineContext.Provider>
    );
};

export const InteractiveSearch = () => (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column' }}>
        <MockMachineProvider>
            <ManualViewer defaultDoc="test-manual.pdf" />
        </MockMachineProvider>
    </div>
);

export const WithAICitation = () => (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column' }}>
        <MockMachineProvider>
            <ManualViewer
                defaultDoc="test-manual.pdf"
                selectedCitation={{
                    docName: 'test-manual.pdf',
                    page: 1,
                    snippet: 'This is an example AI snippet highlight'
                }}
            />
        </MockMachineProvider>
    </div>
);
