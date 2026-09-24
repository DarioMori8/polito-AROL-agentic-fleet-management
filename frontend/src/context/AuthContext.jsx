import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { MOCK_USERS } from '../assets/mocks/MOCK_USERS';

export const AuthContext = createContext(null);

const SESSION_KEY = 'arol_auth_session';

/**
 * AuthProvider
 *
 * Manages the full authentication lifecycle:
 *   - Session persistence via sessionStorage
 *   - login(email, password) — mock today, ready for real API
 *   - logout() — clears session and redirects
 *   - Exposes user = { user_id, company_id, email, first_name, last_name, token }
 *
 * SWITCHING TO REAL AUTH:
 *   Replace the mock block in `login()` with:
 *     const response = await fetch('/v1/auth/login', {
 *       method: 'POST',
 *       headers: { 'Content-Type': 'application/json' },
 *       body: JSON.stringify({ email, password })
 *     });
 *     if (!response.ok) throw new Error('Credenziali non valide.');
 *     const userData = await response.json(); // { token, user_id, company_id, ... }
 */
export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [authLoading, setAuthLoading] = useState(true); // true while reading sessionStorage

    const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';
    const USE_MOCK = import.meta.env?.VITE_USE_MOCK === 'true';

    // On mount: restore session from sessionStorage (survives page refresh)
    useEffect(() => {
        try {
            const saved = sessionStorage.getItem(SESSION_KEY);
            if (saved) {
                setUser(JSON.parse(saved));
            }
        } catch (e) {
            console.warn('AuthContext: failed to restore session from sessionStorage:', e);
        } finally {
            setAuthLoading(false);
        }
    }, []);

    /**
     * Attempt login with email + password.
     * Returns { ok: true } on success, { ok: false, message: string } on failure.
     */
    const login = useCallback(async (email, password) => {
        // ── MOCK MODE ────────────────────────────────────────────────────────
        if (USE_MOCK) {
            await new Promise(resolve => setTimeout(resolve, 500)); // simulate network
            const found = MOCK_USERS.find(
                u => u.email.toLowerCase() === email.trim().toLowerCase() && u.password === password
            );
            if (!found) {
                return { ok: false, message: 'Email o password non corretti.' };
            }
            const sessionData = {
                user_id:    found.user_id,
                company_id: found.company_id,
                company_name: found.company_name,
                email:      found.email,
                first_name: found.first_name,
                last_name:  found.last_name,
                visibility: found.visibility,
                token:      found.token
            };
            sessionStorage.setItem(SESSION_KEY, JSON.stringify(sessionData));
            setUser(sessionData);
            return { ok: true };
        }

        // ── REAL MODE ─────────────────────────────────────────────────────────
        try {
            const response = await fetch(`${API_BASE_URL}/v1/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email.trim(), password })
            });
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                return { ok: false, message: errData.detail || `Errore ${response.status}` };
            }
            const data = await response.json();
            // Expected: { token, user_id, company_id, company_name, email, first_name, last_name, visibility }
            const sessionData = {
                user_id:      data.user_id,
                company_id:   data.company_id,
                company_name: data.company_name,
                email:        data.email,
                first_name:   data.first_name,
                last_name:    data.last_name,
                visibility:   data.visibility,
                token:        data.token
            };
            sessionStorage.setItem(SESSION_KEY, JSON.stringify(sessionData));
            setUser(sessionData);
            return { ok: true };
        } catch (err) {
            console.error('AuthContext login error:', err);
            return { ok: false, message: 'Impossibile connettersi al server. Controlla la rete.' };
        }
    }, [API_BASE_URL, USE_MOCK]);

    /**
     * Clears the current session. Navigation to /login is handled by the caller
     * (ProtectedRoute / FleetView) to avoid coupling AuthContext to the router.
     */
    const logout = useCallback(() => {
        sessionStorage.removeItem(SESSION_KEY);
        // Also clear any cached machine/fleet data that could leak between users
        sessionStorage.removeItem('arol_cached_fleet');
        sessionStorage.removeItem('arol_active_machine');
        sessionStorage.removeItem('arol_active_manuals');
        setUser(null);
    }, []);

    const isAuthenticated = !!user;

    return (
        <AuthContext.Provider value={{ user, isAuthenticated, authLoading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

/**
 * Custom hook to consume the auth context.
 */
export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
    return ctx;
}
