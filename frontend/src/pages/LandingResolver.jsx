import React from 'react';
import { useParams, useNavigate } from 'react-router';
import LandingQR from './LandingQR';

/**
 * LandingResolver Component
 * Simple intermediate route component to extract parameters and render LandingQR
 */
export default function LandingResolver() {
    const { id } = useParams();
    const navigate = useNavigate();

    const handleScanSuccess = (machineId) => {
        // Navigate directly to the conversational workspace upon success
        navigate(`/workspace/${machineId}`);
    };

    const handleNavigateToFleet = () => {
        navigate('/');
    };

    return (
        <LandingQR
            machineIdFromRoute={id}
            onScanSuccess={handleScanSuccess}
            onNavigateToFleet={handleNavigateToFleet}
        />
    );
}