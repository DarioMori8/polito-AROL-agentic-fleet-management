import { BrowserRouter as Router, Routes, Route } from 'react-router';
import LandingResolver from './pages/LandingResolver';
import FleetView from './pages/FleetView';
import WorkspaceWrapper from './pages/WorkspaceWrapper';
import MachineScanner from './pages/MachineScanner';
import './styles/App.css';
import { MachineProvider } from './context/MachineContext';

/**
 * Root Entry Point with standard React Router configuration
 */
export default function App() {
  return (
    <MachineProvider>
      <Router>
        <div className="app-viewport">
          <Routes>
            {/* Main Fleet View Route */}
            <Route path="/" element={<FleetView />} />
            <Route path="/fleet" element={<FleetView />} />

            {/* QR Scan Landing and Resolution Route */}
            <Route path="/machine/:id" element={<LandingResolver />} />

            {/* Conversational and Diagnostic Workspace Route */}
            <Route path="/workspace/:id" element={<WorkspaceWrapper />} />

            {/* Machine Scanner Route */}
            <Route path="/scanner" element={<MachineScanner />} />
          </Routes>
        </div>
      </Router>
    </MachineProvider>
  );
}