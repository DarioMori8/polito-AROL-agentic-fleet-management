import React, { useEffect } from 'react';
import { useNavigate } from 'react-router';
import { Html5QrcodeScanner } from 'html5-qrcode';
import { ScanLine, ShieldCheck } from 'lucide-react';
import Header from '../components/ui/Header';
import '../styles/MachineScanner.css';

const MachineScanner = () => {
    const navigate = useNavigate();

    useEffect(() => {
        // Scanner configuration
        const scanner = new Html5QrcodeScanner(
            "qr-reader", // HTML div id
            {
                fps: 10,
                qrbox: { width: 240, height: 240 },
                rememberLastUsedCamera: true
            },
            false
        );

        // Success logic
        const onScanSuccess = (decodedText) => {
            scanner.clear();

            try {
                // If the QR code is the complete URL
                const url = new URL(decodedText);

                // Navigate using React's internal routing
                navigate(url.pathname);
            } catch (error) {
                // If QR code is only machine id
                navigate(`/machine/${decodedText}`);
            }
        };

        // Continuous error logic
        const onScanFailure = (error) => { };

        // Start scanner
        scanner.render(onScanSuccess, onScanFailure);

        // Cleanup function
        return () => {
            scanner.clear().catch(error => {
                console.error("Error clearing scanner:", error);
            });
        };
    }, [navigate]);

    return (
        <div className="scanner-page">
            <Header onBackClick={() => navigate('/')} />

            <main className="scanner-body">
                {/* Instruction card */}
                <div className="scanner-instruction-card">
                    <div className="scanner-icon-ring">
                        <ScanLine size={32} />
                    </div>
                    <h1 className="scanner-title">Scansiona Macchinario</h1>
                    <p className="scanner-subtitle">
                        Inquadra il QR code del macchinario per accedere al workspace di diagnostica
                    </p>
                </div>

                {/* QR reader */}
                <div className="scanner-reader-wrapper">
                    <div id="qr-reader" />
                </div>

                {/* Footer hint */}
                <p className="scanner-footer-hint">
                    <ShieldCheck size={14} />
                    Connessione sicura · Rete AROL
                </p>
            </main>
        </div>
    );
};

export default MachineScanner;