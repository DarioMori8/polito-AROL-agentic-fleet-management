import React, { useState } from 'react';
import { Navigate, useNavigate, useLocation } from 'react-router';
import { LogIn, Mail, Lock, ShieldAlert, Factory } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import '../styles/LoginPage.css';

/**
 * LoginPage
 *
 * Industrial-style login screen for plant operators.
 * After a successful login, redirects to location.state.from (set by ProtectedRoute)
 * or falls back to the Fleet View at '/'.
 */
export default function LoginPage() {
    const { login, isAuthenticated } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [errorMsg, setErrorMsg] = useState('');

    // If already authenticated, redirect away from the login page.
    // Use <Navigate> instead of navigate(): calling navigate() during render
    // is a React violation that causes a silent white-screen crash.
    const destination = location.state?.from?.pathname || '/';
    if (isAuthenticated) {
        return <Navigate to={destination} replace />;
    }

    const handleSubmit = async (e) => {
        e.preventDefault();
        setErrorMsg('');
        setIsLoading(true);

        const result = await login(email, password);

        setIsLoading(false);

        if (result.ok) {
            navigate(destination, { replace: true });
        } else {
            setErrorMsg(result.message);
        }
    };

    return (
        <div className="login-layout">
            {/* Simulated industrial mesh grid pattern */}
            <div className="industrial-mesh-overlay" />

            <div className="login-card">
                {/* Brand Header */}
                <header className="login-logo-header">
                    <div className="brand-badge">AROL Group</div>
                    <h1 className="login-platform-title">Fleet Management Portal</h1>
                    <p className="login-platform-sub">Smart Factory Agentic Platform</p>
                </header>

                <main className="login-main">
                    <div className="login-icon-ring">
                        <Factory size={28} />
                    </div>
                    <h2 className="login-headline">Accesso Operatore</h2>
                    <p className="login-subtext">
                        Inserisci le tue credenziali aziendali per accedere alla flotta
                    </p>

                    {/* Error banner */}
                    {errorMsg && (
                        <div className="login-error-banner">
                            <ShieldAlert size={15} />
                            <span>{errorMsg}</span>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="login-form" noValidate>
                        {/* Email field */}
                        <div className="login-field">
                            <label htmlFor="login-email" className="login-label">
                                Email aziendale
                            </label>
                            <div className="login-input-wrapper">
                                <Mail size={16} className="login-input-icon" />
                                <input
                                    id="login-email"
                                    type="email"
                                    autoComplete="email"
                                    placeholder="nome.cognome@azienda.it"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    className="login-input"
                                    required
                                    disabled={isLoading}
                                />
                            </div>
                        </div>

                        {/* Password field */}
                        <div className="login-field">
                            <label htmlFor="login-password" className="login-label">
                                Password
                            </label>
                            <div className="login-input-wrapper">
                                <Lock size={16} className="login-input-icon" />
                                <input
                                    id="login-password"
                                    type="password"
                                    autoComplete="current-password"
                                    placeholder="••••••••"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="login-input"
                                    required
                                    disabled={isLoading}
                                />
                            </div>
                        </div>

                        {/* Submit */}
                        <button
                            type="submit"
                            className="login-submit-btn"
                            disabled={isLoading || !email || !password}
                        >
                            {isLoading ? (
                                <>
                                    <span className="login-spinner" />
                                    Verifica credenziali...
                                </>
                            ) : (
                                <>
                                    <LogIn size={16} />
                                    Accedi
                                </>
                            )}
                        </button>
                    </form>
                </main>

                <footer className="login-footer">
                    <p>© 2026 AROL Group S.p.A. • Canelli (AT)</p>
                    <span className="login-footer-tag">Accesso sicuro · Rete AROL</span>
                </footer>
            </div>
        </div>
    );
}
