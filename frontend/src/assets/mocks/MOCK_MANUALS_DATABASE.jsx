export const MOCK_MANUALS_DATABASE = {
    'Manuale_Euro_VP_Manutenzione.pdf': {
        title: 'AROL Euro VP - Use & Maintenance Manual',
        totalPages: 80,
        pages: {
            24: {
                section: 'Section 4.1 - Preventive Maintenance Scheduler',
                title: 'IDLE ROLLERS LUBRICATION & SERVICE INTERVALS',
                text: 'Routine inspection and lubrication of the idle rollers on the Euro VP capping head must be conducted every 500 operating hours. In high-humidity bottling lines, reduce this interval to 300 hours. Immediate manual lubrication is mandatory if the telemetry system triggers the vibration alarm AL-VIB-02.',
                specs: [
                    { label: 'Lubricant Type', value: 'AROL Food-Grade Grease Synthetic-3' },
                    { label: 'Check Interval', value: '500 Hours (Standard) / 300 Hours (Wet environment)' },
                    { label: 'Related Alarm', value: 'AL-VIB-02 (Vibration Out of Range)' }
                ],
                blueprintType: 'roller'
            },
            42: {
                section: 'Section 4.2 - Vibration Diagnostics',
                title: 'VIBRATION ANOMALIES & CAM ALIGNMENT',
                text: 'Excessive baseplate vibration often originates from loose anchoring bolts or uneven pressure distribution along the capping track. Inspect the idle guide rollers for structural wear. Tighten anchor bolts to the certified specifications. If vibrations continue to exceed threshold limits, check and manually align the main capping closing cam.',
                specs: [
                    { label: 'Primary Cam Clearances', value: '0.05 mm - 0.12 mm' },
                    { label: 'Anchor Bolt Torque', value: '120.0 Nm' },
                    { label: 'Inspection Points', value: 'Capping Head Basement, Idle Guide Rollers, Roller Bearings' }
                ],
                blueprintType: 'cam'
            }
        }
    },
    'Specifiche_Ancoraggio_AROL.pdf': {
        title: 'AROL Structural Anchoring & Installation Specs',
        totalPages: 30,
        pages: {
            15: {
                section: 'Section 2.3 - Heavy Duty Anchoring',
                title: 'BASEPLATE STABILIZATION & MECHANICAL ANCHORING',
                text: 'To minimize operational harmonics and high-torque mechanical resonance, capping machines must be rigidly bolted using M16 class 8.8 threaded anchors. The concrete foundation must be fully cured (min. 28 days) with a minimum compressive strength of 25 MPa. Ensure uniform torque distribution using a calibrated torque wrench.',
                specs: [
                    { label: 'Bolt Spec', value: 'M16 Threaded Rod, Class 8.8 Steel' },
                    { label: 'Target Tightening Torque', value: '120.0 Nm (±5 Nm Tolerance)' },
                    { label: 'Minimum Concrete Depth', value: '150.0 mm' }
                ],
                blueprintType: 'anchor'
            }
        }
    },
    'Specifiche_Serraggio_Q2.pdf': {
        title: 'AROL Mechanical Torque & Thermal Tolerances',
        totalPages: 18,
        pages: {
            8: {
                section: 'Section 1.8 - Motor Thermal Thresholds',
                title: 'MOTOR THERMAL LIMITS & CAPPING TORQUE COEFFICIENTS',
                text: 'The main motor drive assembly is designed to operate continuously under a baseplate temperature limit of 60.0 °C. Exceeding 65.0 °C triggers automatic telemetry warnings. Capping torque coefficients for the Euro VP capping jaws must be maintained at an optimal value of 14.2 Nm to prevent bottle closure deformation or leakage.',
                specs: [
                    { label: 'Max Baseplate Temp', value: '60.0 °C (Operational Limit) / 65.0 °C (Critical Threshold)' },
                    { label: 'Optimal Capping Torque', value: '14.2 Nm' },
                    { label: 'Power Supply Coefficient', value: '400V / 50Hz (Stabilized)' }
                ],
                blueprintType: 'motor'
            }
        }
    }
};
