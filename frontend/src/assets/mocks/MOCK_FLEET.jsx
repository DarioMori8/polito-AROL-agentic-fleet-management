// Mock Fleet Dataset matching AROL Project Specifications
// company_id added to support auth-based fleet filtering
export const MOCK_FLEET = [
    {
        id: "001",
        company_id: "CMP-001",
        name: "AROL Capper #12",
        model: "Euro VP",
        model_id: "MDL-100",
        serial_number: "AR-EVP-2026-098",
        status: "maintenance", // Renders warning state in UI
        location: "Bottling Line B (Canelli)",
        plant_location: "Bottling Line B (Canelli)"
    },
    {
        id: "002",
        company_id: "CMP-001",
        name: "AROL Labeller #4",
        model: "Decolleté 3000",
        model_id: "MDL-200",
        serial_number: "AR-DEC-2025-102",
        status: "online", // Renders success state in UI
        location: "Packaging Hall A",
        plant_location: "Packaging Hall A"
    },
    {
        id: "003",
        company_id: "CMP-002",
        name: "AROL Filler #9",
        model: "Isobaric Glass 40",
        model_id: "MDL-300",
        serial_number: "AR-ISO-2024-441",
        status: "online",
        location: "Filling Dept 2",
        plant_location: "Filling Dept 2"
    }
];
