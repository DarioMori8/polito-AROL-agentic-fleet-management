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
    const { isAuthenticated, authLoading } = useAuth();
    const location = useLocation();

    // While sessionStorage is being read on first mount, render nothing to
    // avoid a flash-redirect to /login for users with a valid session.
    if (authLoading) return null;

    if (!isAuthenticated) {
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    return children;
}
