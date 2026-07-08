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
