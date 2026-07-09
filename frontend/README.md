# AROL Fleet Management — Frontend

Mobile-first PWA for industrial machine maintenance, built with the **Rugged UI** design system optimized for gloved use on factory floors.

## Tech Stack

| Layer         | Technology                          |
|---------------|-------------------------------------|
| Framework     | React 19 + Vite 8                   |
| PWA           | vite-plugin-pwa (service worker, offline support) |
| Linting       | ESLint 10 (react-hooks, react-refresh) |
| Testing       | Vitest + Playwright (browser tests) |
| Component Dev | Storybook 10                        |
| Styling       | Vanilla CSS (Industrial Design System) |

## Project Structure

```
src/
├── components/
│   ├── chat/          # AI chat agent interface
│   ├── dashboard/     # Machine dashboard widgets
│   ├── manuals/       # Technical manual viewer
│   └── ui/            # Shared UI primitives (Button, ...)
├── context/           # React context providers
├── hooks/             # Custom React hooks
├── pages/             # Top-level page components
├── stories/           # Storybook stories
├── styles/            # Global & component CSS
├── App.jsx            # Root component
└── main.jsx           # Entry point
```

## Visual Flow & Routing Architecture

```text
================================================================================
   🗺️ VISUAL FLOW & ROUTING ARCHITECTURE — AROL CHATBOT PLATFORM (react-router)
================================================================================

              [ PHYSICAL SCAN ] 
               Scan of QR Code 
                      │
                      ▼
     Route: "/machine/:id" (LandingQR) <───[ MANUAL CLICK ]─── Route: "/" or "/fleet" (FleetView)
     ─────────────────────────────────                         ─────────────────────────────────
     * Component: <LandingResolver />                          * Component: <FleetView />
     * State: loading | error                                  * Actions: Search & Filter [1]
     * Action: scanMachine(id) [2]                             * Event: onClick ➔ navigate(`/machine/${id}`)
                      │
                      │ (Auto-resolves context [2])
                      ▼
     Route: "/workspace/:id" (ChatWorkspace)
     ────────────────────────────────────────
     * Component: <WorkspaceWrapper /> ➔ <ChatWorkspace />
     * Layout: Mobile (Tabbed View) vs Tablet (Split-Screen) [1]
     * App States: Messages, isAiLoading, Active Machine Context [3]
     │
     ├─► [Tab 1] Route Path ➔ "chat"
     │           * Component: <ChatWindow />
     │           * UI: <ChatBubble /> [4] + <SuggestionChips /> + <ChatInput /> [4]
     │
     ├─► [Tab 2] Route Path ➔ "manuals" (RAG)
     │           * Component: <ManualViewer />
     │           * Content: PDF rendering with targeted page jumping (via citations) [2]
     │
     ├─► [Tab 3] Route Path ➔ "iot"
     │           * Component: <RealTimeChart />
     │           * Content: Real-time telemetry widgets (Motor Temperature, Torque) [5]
     │
     └─► [Action] "Nuova Scansione" ➔ clearMachine() ➔ navigate("/")
```

## Getting Started



```bash
# Install dependencies
npm install

# Start dev server (http://localhost:3000)
npm run dev

# Lint
npm run lint

# Run Storybook
npm run storybook

# Run tests
npx vitest
```

## Key Configuration

- **Path alias**: `@` → `src/` (e.g. `import Button from '@/components/ui/Button'`)
- **Dev server**: port `3000`, exposed on LAN (`host: true`) for mobile testing via QR code
- **PWA manifest**: `AROL Multi-Agent Platform`, standalone, portrait orientation

## Design System (Rugged UI)

Optimized for industrial environments with high-contrast colors and touch targets ≥ 48px (WCAG 2.1).

| Token            | Value     | Usage                        |
|------------------|-----------|------------------------------|
| `--arol-blue`    | `#002D54` | Primary actions              |
| `--arol-sky`     | `#407B9E` | Secondary / interactive      |
| `--arol-red`     | `#C0392B` | Alarms / critical errors     |
| `--arol-green`   | `#27AE60` | Operational / confirmations  |
| `--arol-dark`    | `#1A252F` | Text on light backgrounds    |
