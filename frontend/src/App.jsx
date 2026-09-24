import { BrowserRouter as Router, Routes, Route } from 'react-router';
import LandingResolver from './pages/LandingResolver';
import FleetView from './pages/FleetView';
import WorkspaceWrapper from './pages/WorkspaceWrapper';
import MachineScanner from './pages/MachineScanner';
import LoginPage from './pages/LoginPage';
import './styles/App.css';
import { MachineProvider } from './context/MachineContext';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ui/ProtectedRoute';

/**
 * Root Entry Point with React Router and Authentication layer.
 *
 * Route access model:
 *   PUBLIC      /login              → LoginPage
 *   PROTECTED   / /fleet /scanner   → require login
 *   SEMI-PUBLIC /machine/:id        → always visible (info + PDF), chat requires login
 *   SEMI-PUBLIC /workspace/:id      → PDF always visible, chat blocked until login
 */
export default function App() {
    return (
        <AuthProvider>
            <MachineProvider>
                <Router>
                    <div className="app-viewport">
                        <Routes>
                            {/* Public route */}
                            <Route path="/login" element={<LoginPage />} />

                            {/* Protected routes — require authentication */}
                            <Route path="/" element={
                                <ProtectedRoute><FleetView /></ProtectedRoute>
                            } />
                            <Route path="/fleet" element={
                                <ProtectedRoute><FleetView /></ProtectedRoute>
                            } />
                            <Route path="/scanner" element={
                                <ProtectedRoute><MachineScanner /></ProtectedRoute>
                            } />

                            {/* Semi-public routes — accessible without login,
                                but chat AI requires authentication (handled internally) */}
                            <Route path="/machine/:id" element={<LandingResolver />} />
                            <Route path="/workspace/:id" element={<WorkspaceWrapper />} />
                        </Routes>
                    </div>
                </Router>
            </MachineProvider>
        </AuthProvider>
    );
}