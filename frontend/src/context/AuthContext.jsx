import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { MOCK_USERS } from '../assets/mocks/MOCK_USERS';

export const AuthContext = createContext(null);

const SESSION_KEY = 'arol_auth_session';

/**
 * Maps the backend UserOut schema to our internal session shape.
 * Backend: { id, company_id, first_name, last_name, email, job_title, visibility }
 * Internal: { user_id, company_id, email, first_name, last_name, job_title, visibility }
 */
function mapUserOut(data) {
    return {
        user_id: data.id,            // backend calls it "id"
        company_id: data.company_id,
        email: data.email,
        first_name: data.first_name,
        last_name: data.last_name,
        job_title: data.job_title,
        visibility: data.visibility,
        // note: company_name is not exposed by the backend UserOut schema
    };
}

/**
 * AuthProvider
 *
 * Manages the full authentication lifecycle:
 *   - Session persistence (mock: sessionStorage / real: httpOnly cookie)
 *   - login(email, password) — mock today, ready for real API
 *   - logout() — invalidates server session + clears local state
 *   - Exposes user = { user_id, company_id, email, first_name, last_name, job_title, visibility }
 *
 * Auth strategy (REAL MODE):
 *   Backend uses server-side sessions with an httpOnly cookie (`arol_session`).
 *   The browser sends the cookie automatically on every same-origin request —
 *   NO Authorization header is needed anywhere in the app.
 *
 *   Endpoints:
 *     POST   /v1/sessions          → login  (sets cookie, returns UserOut)
 *     GET    /v1/sessions/current  → whoami (validates cookie, returns UserOut)
 *     DELETE /v1/sessions/current  → logout (clears cookie server-side)
 */
export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [authLoading, setAuthLoading] = useState(true); // true while session is being resolved

    const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';
    const USE_MOCK = import.meta.env?.VITE_USE_MOCK === 'true';

    // ── MOUNT: resolve any existing session ─────────────────────────────────────
    useEffect(() => {
        if (USE_MOCK) {
            // Mock: the "cookie" is simulated via sessionStorage
            try {
                const saved = sessionStorage.getItem(SESSION_KEY);
                if (saved) setUser(JSON.parse(saved));
            } catch (e) {
                console.warn('AuthContext: failed to restore mock session:', e);
            }
            setAuthLoading(false);
            return;
        }

        // Real: validate whether the browser cookie is still active.
        // sessionStorage is used as a fast display cache to avoid UI flash on refresh,
        // but the server is always the source of truth.
        const cached = (() => {
            try {
                const s = sessionStorage.getItem(SESSION_KEY);
                return s ? JSON.parse(s) : null;
            } catch { return null; }
        })();
        if (cached) setUser(cached); // instant restore from cache (no flash)

        fetch(`${API_BASE_URL}/v1/sessions/current`, {
            credentials: 'include', // send the arol_session cookie
        })
            .then(res => res.ok ? res.json() : null)
            .then(data => {
                if (data) {
                    const sessionData = mapUserOut(data);
                    sessionStorage.setItem(SESSION_KEY, JSON.stringify(sessionData));
                    setUser(sessionData);
                } else {
                    // Cookie expired or invalid → clear stale cache
                    sessionStorage.removeItem(SESSION_KEY);
                    setUser(null);
                }
            })
            .catch(() => {
                // Network error: keep the cached user so the app works offline,
                // but do not block the UI.
                console.warn('AuthContext: could not validate session with server.');
            })
            .finally(() => setAuthLoading(false));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // ── LOGIN ────────────────────────────────────────────────────────────────────
    /**
     * Attempt login with email + password.
     * Returns { ok: true } on success, { ok: false, message: string } on failure.
     */
    const login = useCallback(async (email, password) => {
        // ── MOCK MODE ─────────────────────────────────────────────────────────────
        if (USE_MOCK) {
            await new Promise(resolve => setTimeout(resolve, 500)); // simulate network
            const found = MOCK_USERS.find(
                u => u.email.toLowerCase() === email.trim().toLowerCase() && u.password === password
            );
            if (!found) {
                return { ok: false, message: 'Email o password non corretti.' };
            }
            const sessionData = {
                user_id: found.user_id,
                company_id: found.company_id,
                company_name: found.company_name,
                email: found.email,
                first_name: found.first_name,
                last_name: found.last_name,
                visibility: found.visibility,
                token: found.token
            };
            sessionStorage.setItem(SESSION_KEY, JSON.stringify(sessionData));
            setUser(sessionData);
            return { ok: true };
        }

        // ── REAL MODE ─────────────────────────────────────────────────────────────
        // POST /v1/sessions — the server sets the arol_session cookie on 201 Created.
        // The response body is UserOut: no token field, no company_name.
        try {
            const response = await fetch(`${API_BASE_URL}/v1/sessions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include', // required to receive the Set-Cookie header cross-origin
                body: JSON.stringify({ email: email.trim(), password })
            });
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                return { ok: false, message: errData.detail || `Errore ${response.status}` };
            }
            const data = await response.json();
            const sessionData = mapUserOut(data);
            // Cache user info for fast restore on refresh (the cookie is the real token)
            sessionStorage.setItem(SESSION_KEY, JSON.stringify(sessionData));
            setUser(sessionData);
            return { ok: true };
        } catch (err) {
            console.error('AuthContext login error:', err);
            return { ok: false, message: 'Impossibile connettersi al server. Controlla la rete.' };
        }
    }, [API_BASE_URL, USE_MOCK]);

    /**
     * Login as guest user, with limited functionalities active in the application.
     * Used to directly login by scanning a qr code on a machine.
     * Will require a second login to unlock the chatbot and the fleet view.
     */
    const loginAsGuest = useCallback(async (guestToken) => {
        try {
            const response = await fetch(`${API_BASE_URL}/v1/sessions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ guest_token: guestToken })
            });
            if (!response.ok) return { ok: false }
            const data = await response.json()
            const sessionData = { ...mapUserOut(data), is_guest: true }
            sessionStorage.setItem(SESSION_KEY, JSON.stringify(sessionData))
            setUser(sessionData)
            return { ok: true }
        } catch { return { ok: false } }
    }, [API_BASE_URL]);

    // ── LOGOUT ───────────────────────────────────────────────────────────────────
    /**
     * Invalidates the server session (DELETE /v1/sessions/current) then clears
     * all local state. Navigation to /login is handled by the caller to avoid
     * coupling AuthContext to the router.
     *
     * Made async so callers can `await logout()` before navigating.
     */
    const logout = useCallback(async () => {
        if (!USE_MOCK) {
            try {
                await fetch(`${API_BASE_URL}/v1/sessions/current`, {
                    method: 'DELETE',
                    credentials: 'include',
                });
            } catch {
                // Best-effort: even if the server call fails, clear local state
                // so the user is not stuck in a broken authenticated UI.
            }
        }
        // Clear local caches that could leak data between users
        sessionStorage.removeItem(SESSION_KEY);
        sessionStorage.removeItem('arol_cached_fleet');
        sessionStorage.removeItem('arol_active_machine');
        sessionStorage.removeItem('arol_active_manuals');
        setUser(null);
    }, [API_BASE_URL, USE_MOCK]);

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
