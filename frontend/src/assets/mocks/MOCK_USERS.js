/**
 * MOCK_USERS — Fake user accounts for frontend auth simulation.
 *
 * Each user belongs to a company (company_id), which maps to the MOCK_FLEET
 * company_id field. When logged in, the fleet is filtered to show only
 * machines from the user's company.
 *
 * COMPANY MAPPING:
 *   CMP-001 → Machines 001, 002 (AROL Capper #12, AROL Labeller #4)
 *   CMP-002 → Machine 003 (AROL Filler #9)
 *
 * VISIBILITY LEVELS (mirrors backend Visibility enum):
 *   full        → Full access to all machine data and AI chat
 *   technician  → Maintenance-focused access
 *   commercial  → Commercial data access only
 *
 * Switch to REAL MODE: replace AuthContext.login() body with:
 *   POST /v1/auth/login  { email, password }
 *   Expected response: { token, user_id, company_id, email, first_name, last_name }
 */
export const MOCK_USERS = [
    {
        user_id: "USR-001",
        company_id: "CMP-001",
        company_name: "Distillerie Beccaris S.r.l.",
        first_name: "Marco",
        last_name: "Bianchi",
        email: "marco.bianchi@beccaris.it",
        password: "arol2026",
        visibility: "full",
        token: "mock-jwt-token-usr001-cmp001"
    },
    {
        user_id: "USR-002",
        company_id: "CMP-001",
        company_name: "Distillerie Beccaris S.r.l.",
        first_name: "Sofia",
        last_name: "Rossi",
        email: "sofia.rossi@beccaris.it",
        password: "technician1",
        visibility: "technician",
        token: "mock-jwt-token-usr002-cmp001"
    },
    {
        user_id: "USR-003",
        company_id: "CMP-002",
        company_name: "Oleificio Nuoro S.p.A.",
        first_name: "Luca",
        last_name: "Ferretti",
        email: "luca.ferretti@oleificionuoro.it",
        password: "nuoro2026",
        visibility: "full",
        token: "mock-jwt-token-usr003-cmp002"
    }
];
