import React from 'react';
import { Navigate, useLocation } from 'react-router';
import { useAuth } from '../../context/AuthContext';

/**
 * ProtectedRoute
 *
 * Wraps a route element and redirects unauthenticated users to /login.
 * Preserves the original destination in location.state.from so LoginPage
 * can redirect back after a successful login.
 *
 * Usage in App.jsx:
 *   <Route path="/" element={<ProtectedRoute><FleetView /></ProtectedRoute>} />
 */
export default function ProtectedRoute({ children }) {
    const { isAuthenticated, authLoading, user } = useAuth();
    const location = useLocation();

    // While sessionStorage is being read on first mount, render nothing to
    // avoid a flash-redirect to /login for users with a valid session.
    if (authLoading) return null;

    // Guest user (is_guest: true) are NOT allowed into protected routes (fleet view, scanner).
    // They can only access /workspace/:id (with restricted functionalities)

    if (!isAuthenticated || user?.is_guest) {
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    return children;
}
