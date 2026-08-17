import React, { useEffect } from 'react';
import { useNavigate } from 'react-router';
import { Html5QrcodeScanner } from 'html5-qrcode';

const MachineScanner = () => {
    const navigate = useNavigate();

    useEffect(() => {
        // Scanner configuration
        const scanner = new Html5QrcodeScanner(
            "qr-reader", // HTML div id
            {
                fps: 10,
                qrbox: { width: 250, height: 250 },
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
                navigate(`/machines/${decodedText}`);
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
        <div className='scanner-container'>
            <div id="qr-reader"></div>
        </div>
    )
}

export default MachineScanner;