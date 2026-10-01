import React from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router';
import LandingQR from './LandingQR';

/**
 * LandingResolver Component
 * Simple intermediate route component to extract parameters and render LandingQR
 * Also handle automatic guest login (when scanning a QR code)
 */
export default function LandingResolver() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [searchParams] = useSearchParams()
    const { isAuthenticated, loginAsGuest } = useAuth()
    const [guestLoginDone, setGuestLoginDone] = useState(false)

    // Auto login as guest
    // If URL contains ?guest_token=<token> and user is not yet logged in
    useEffect(() => {
        const guestToken = searchParams.get('guest_token')
        if (!guestToken || isAuthenticated || guestLoginDone) return;
        loginAsGuest(guestToken).then(({ ok }) => {
            setGuestLoginDone(true)
            if (!ok) console.warn('LandingResolver: guest token rejected by the server.')
        })
    }, [searchParams, isAuthenticated, guestLoginDone, loginAsGuest])

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