# AROL Multi-Agent Conversational Ecosystem — Frontend Client

Mobile-first Progressive Web Application (PWA) per tecnici di manutenzione e operatori di stabilimento industriale. Costruita sul design language **AROL Rugged UI**, ottimizzata per visibilità ad alto contrasto e interazioni touch con guanti su dispositivi rugged (smartphone, tablet, PMA industriali).

Il frontend è l'interfaccia utente dell'ecosistema conversazionale AROL: permette di scansionare QR code delle macchine, consultare un troubleshooter AI multi-agente, ricevere risposte in streaming SSE token-by-token, visualizzare i segmenti di manuale recuperati dal RAG (ChromaDB) nel viewer PDF integrato, e gestire la cronologia delle conversazioni per macchina.

---

## 🛠️ Tech Stack

| Layer | Tecnologia | Note |
| :--- | :--- | :--- |
| **Framework** | React 19 + Vite 8 | SPA ottimizzata per basso footprint mobile |
| **Routing** | React Router v8 | Route: `/`, `/fleet`, `/machine/:id`, `/workspace/:id`, `/scanner` |
| **Icons** | Lucide React | Iconografia industriale ad alto contrasto |
| **PWA Layer** | `vite-plugin-pwa` | Manifest, service worker con `autoUpdate`, icone 192/512px |
| **Styling** | Vanilla CSS3 | Design token centralizzati in `styles/tokens.css` |
| **QR Scanner** | `html5-qrcode` | Scansione QR code nativa da fotocamera |
| **PDF Viewer** | `react-pdf` v10 | Visualizzatore manuali tecnici AROL con text extraction |
| **Markdown** | `react-markdown` + `remark-gfm` | Rendering GFM completo: tabelle, bold, code, liste, ecc. |
| **Testing** | Vitest + Playwright | Test Storybook via `@storybook/addon-vitest` |
| **Component Docs** | Storybook 10 | Dev server su porta `6006` |
| **Production Server** | Nginx (Alpine) | SPA fallback con `try_files $uri /index.html` |

### Configurazioni Chiave
- **Path Alias**: `@` → `src/` (es. `import Button from '@/components/ui/Button'`)
- **Dev Server**: porta `3000`, `host: true` — esposto in LAN per test su dispositivi fisici
- **PWA Display**: `standalone`, orientamento `portrait`, tema `#002D54` (blu AROL)
- **Mock Mode**: `VITE_USE_MOCK=true` attiva la simulazione SSE locale per sviluppo offline

---

## 🎨 Design System (Rugged UI)

Progettato per ambienti industriali con illuminazione variabile e uso con guanti. Tutti i touch target sono **≥ 48px** (WCAG 2.1).

### Token (`src/styles/tokens.css`)

| Token CSS | Valore | Utilizzo |
| :--- | :--- | :--- |
| `--arol-blue` | `#002D54` | Messaggi utente, header, bottoni primari |
| `--arol-sky` | `#407B9E` | Citazioni, link, stati attivi secondari |
| `--arol-sky-light` | `rgba(64,123,158,0.12)` | Background citation cards |
| `--arol-dark` | `#1A252F` | Testo ad alta leggibilità |
| `--arol-gray-light` | `#F0F2F5` | Messaggi AI, background pagina |
| `--arol-red` | `#C0392B` | Allarmi, errori di rete |
| `--arol-red-light` | `rgba(192,57,43,0.08)` | Background errori |
| `--arol-green` | `#27AE60` | Stato operativo, successo |
| `--font-primary` | `'Inter'` | Tipografia principale |

**Spacing**: griglia a 4px (`--space-1` → `--space-4`). **Border radius**: `sm/md/lg/xl`.

---

## 📐 Architettura Frontend

### Routing (`App.jsx`)

```
/                → FleetView        (lista flotta macchine)
/fleet           → FleetView        (alias)
/machine/:id     → LandingResolver  → LandingQR (scansione QR + scheda macchina)
/workspace/:id   → WorkspaceWrapper → ChatWorkspace (chat SSE + ManualViewer)
/scanner         → MachineScanner   (scansione manuale via fotocamera)
```

### State Management

```
MachineProvider (React Context globale — MachineContext.jsx)
    ├── fleet[]           → GET /v1/machines
    ├── activeMachine     → GET /v1/machines/{id}
    ├── activeManuals[]   → GET /v1/machines/{id}/manuals
    ├── loading / error
    └── sessionStorage cache  →  arol_cached_fleet, arol_active_machine, arol_active_manuals

WorkspaceWrapper (locale)
    ├── messages[]        → stato locale chat bubbles (modello: ChatMessage.js)
    ├── isAiLoading       → disabilita input durante streaming
    ├── sessionsList[]    → lista sessioni per macchina (localStorage: arol_sessions_{id})
    ├── currentSessionId  → sessione attiva (null = nuova conversazione)
    ├── isDrawerOpen      → visibilità del ChatHistoryDrawer
    ├── useChatStream()   → hook SSE streaming
    └── useChatApi()      → hook REST per fetch storico (GET /v1/conversations/{id}/messages)
```

### Flusso Conversazionale SSE

```
Operatore digita query → WorkspaceWrapper.handleSendMessage()
    │
    │  POST /v1/chat/stream  { query, machine_id, session_id? }
    ▼
useChatStream.streamMessage()
    ├── fetch() + ReadableStream (non EventSource: richiede POST)
    ├── AbortController per cancellazione
    └── Parser SSE frame-by-frame:
        │
        ├── "start"     → acquisisce session_id → onSessionCreated() → salva in localStorage
        ├── "thinking"  → onThinking() → accumula thinkingText nella bolla AI (accordion)
        ├── "token"     → onToken() → aggiorna bolla AI carattere per carattere
        ├── "status"    → (parsato, non mostrato in UI)
        ├── "citations" → onComplete() con citations[] mappati a docName/page/snippet
        ├── "error"     → onError() (recoverable: warn, non-recoverable: throw)
        └── "done"      → salva session_id in localStorage
```

### Flusso Chat History

```
WorkspaceWrapper.initializeChat()  (effetto su cambio activeMachine/id)
    ├── Legge arol_sessions_{machineId} da localStorage
    ├── Se sessioni presenti → carica la più recente
    │       └── useChatApi.fetchChatHistory(sessionId)
    │               └── GET /v1/conversations/{session_id}/messages
    │                   Risposta: ConversationHistory { messages[]{role, content, sources[]} }
    └── Fallback: mostra welcome message (nuova conversazione)

ChatHistoryDrawer
    ├── Lista sessioni passate per la macchina attiva con preview e timestamp
    ├── "Nuova Conversazione" → handleNewChat() → reset messages + sessionId null
    └── Click sessione → handleSelectSession() → ricarica storico dal backend
```

---

## 📂 Struttura del Progetto

```
frontend/
├── public/
│   └── icons/                         # Icone PWA (192x192, 512x512)
├── src/
│   ├── assets/
│   │   └── mocks/
│   │       └── MOCK_MANUALS_DATABASE  # Database mock manuali per sviluppo offline
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatBubble.jsx         # Bolla chat: Markdown GFM, thinking accordion, citazioni, retry
│   │   │   ├── ChatHistoryDrawer.jsx  # Drawer laterale: lista sessioni, nuova chat, selezione sessione
│   │   │   ├── ChatInput.jsx          # Input bar con gestione invio e stato loading
│   │   │   ├── ChatWindow.jsx         # Feed chat: lista bolle + suggestion chips
│   │   │   ├── ChatWindowHeader.jsx   # Header workspace con info macchina attiva
│   │   │   └── SuggestionChips.jsx    # Chip con domande suggerite contestuali
│   │   ├── manuals/
│   │   │   ├── ManualViewer.jsx       # Viewer PDF: zoom, navigazione, citation routing, full-text search
│   │   │   ├── AIReferenceBanner.jsx  # Banner snippet RAG (attualmente disabilitato in ManualViewer)
│   │   │   ├── DocumentArea.jsx       # Area rendering PDF + highlight snippet RAG + search highlight
│   │   │   ├── SearchDrawer.jsx       # Drawer ricerca full-text nel documento aperto
│   │   │   └── TopToolbar.jsx         # Toolbar viewer: selezione documento, zoom, fullscreen, ricerca
│   │   └── ui/
│   │       ├── Button.jsx             # Componente bottone riusabile
│   │       └── Header.jsx             # Header generico condiviso
│   ├── context/
│   │   └── MachineContext.jsx         # Provider flotta: fetch, scan, cache, offline fallback
│   ├── hooks/
│   │   ├── useChatStream.js           # Hook SSE streaming (fetch + ReadableStream) — principale
│   │   └── useChatApi.js              # Hook REST: fetchChatHistory per restore conversazioni
│   ├── models/
│   │   └── ChatMessage.js             # Schema ChatMessage con DEFAULT_CHAT_MESSAGE
│   ├── pages/
│   │   ├── FleetView.jsx              # Dashboard flotta: griglia macchine, filtri, ricerca
│   │   ├── LandingQR.jsx              # Landing post-scansione: scheda macchina + navigazione
│   │   ├── LandingResolver.jsx        # Resolver route /machine/:id → LandingQR
│   │   ├── MachineScanner.jsx         # Scanner QR via fotocamera (html5-qrcode)
│   │   ├── ChatWorkspace.jsx          # Layout workspace: tab mobile / split-screen tablet
│   │   └── WorkspaceWrapper.jsx       # Orchestratore: messaggi, sessioni, SSE, history, drawer
│   ├── stories/                       # Storybook stories per i componenti
│   │   ├── Button.stories.jsx
│   │   ├── ChatBubble.stories.jsx
│   │   ├── ChatInput.stories.jsx
│   │   ├── ChatWindow.stories.jsx
│   │   └── ManualViewer.stories.jsx
│   ├── styles/
│   │   ├── tokens.css                 # ⭐ Design tokens: colori, spacing, radius, font
│   │   ├── base.css                   # Reset CSS globale
│   │   ├── index.css                  # Entry point CSS
│   │   ├── App.css                    # Stili viewport globali
│   │   ├── Button.css
│   │   ├── ChatBubble.css
│   │   ├── ChatHistoryDrawer.css
│   │   ├── ChatInput.css
│   │   ├── ChatWindow.css
│   │   ├── ChatWorkspace.css
│   │   ├── FleetView.css
│   │   ├── Header.css
│   │   ├── LandingQR.css
│   │   ├── MachineScanner.css
│   │   ├── ManualViewer.css
│   │   └── SuggestionChips.css
│   ├── App.jsx                        # Router React + MachineProvider
│   └── main.jsx                       # Entry point React
├── .env                               # VITE_API_URL, VITE_USE_MOCK (non versionato)
├── .env.example                       # Template variabili d'ambiente
├── Dockerfile                         # Multi-stage: build Vite → serve Nginx Alpine
├── nginx.conf                         # SPA fallback + CORS headers
├── vite.config.js                     # Plugin PWA, alias @, server LAN, Vitest+Playwright
└── package.json
```

---

## 🚀 Come Avviare

### Prerequisiti
- **Node.js v20+**
- Backend in esecuzione su `http://localhost:8000` (o configurare `VITE_API_URL`)

### Sviluppo Locale

```bash
# 1. Installa le dipendenze
cd frontend
npm install

# 2. Configura le variabili d'ambiente
cp .env.example .env
# Modifica VITE_API_URL se necessario (default: http://localhost:8000)
# Imposta VITE_USE_MOCK=true per sviluppo offline con simulazione SSE

# 3. Avvia il dev server
npm run dev
# → http://localhost:3000
# → http://<IP-LAN>:3000  (per test su dispositivi fisici in rete)
```

### Storybook (Component Explorer)

```bash
npm run storybook
# → http://localhost:6006
```

### Test

```bash
npm run test        # Vitest + Playwright (headless Chromium)
```

### Build di Produzione

```bash
npm run build       # Output in dist/
npm run preview     # Anteprima locale del build
```

### Con Docker Compose (stack completo)

Il frontend viene avviato automaticamente con l'intero stack. Il container espone la porta `3000` (Nginx), mappata su `8080` dell'host:

```bash
# Dalla root del repository:
docker compose up --build
# → http://localhost:8080
```

---

## 🛡️ Nginx in Produzione

Il Dockerfile usa un build multi-stage: Vite compila il bundle in `/dist`, poi Nginx Alpine serve i file statici. La configurazione include il fallback SPA obbligatorio per React Router:

```nginx
location / {
    root /usr/share/nginx/html;
    index index.html;
    try_files $uri $uri/ /index.html;
}
```

Questo garantisce che deep-link (es. `/workspace/2`) e reload manuali non producano `404`.

---

## 🆕 Last Updates

- ✅ **Toggle "AI Thinking" espandibile** `🔵 Miglioramento`
  Quando l'AI invia eventi `thinking` (ragionamento interno del modello), viene mostrato un elemento collassabile nella bolla AI — un accordion `💭 Mostra ragionamento` — che l'operatore può espandere per vedere il processo decisionale dell'AI. Implementato in `ChatBubble.jsx` tramite il campo `thinkingText`, accumulato da `WorkspaceWrapper` via callback `onThinking` dall'hook `useChatStream`.

- ✅ **Drawer ricerca testo nel PDF** `🟡 UX`
  Il `SearchDrawer.jsx` è ora collegato alla logica di ricerca full-text nel `ManualViewer`. All'apertura di ogni PDF, il testo viene estratto pagina per pagina con `react-pdf` (`getTextContent()`). La ricerca avviene client-side: supporta sia la ricerca per titolo/filename tra tutti i manuali disponibili, sia la ricerca full-text nel documento aperto, con navigazione diretta alla pagina del match.

- ✅ **Implementazione frontend Chat History**
  Gestione completa della cronologia delle conversazioni per macchina. Le sessioni sono salvate in `localStorage` (`arol_sessions_{machineId}`). All'init, `WorkspaceWrapper` carica automaticamente l'ultima sessione dal backend via `GET /v1/conversations/{session_id}/messages`, ricostruendo la cronologia con i rispettivi messaggi e citazioni. Il componente `ChatHistoryDrawer` permette di navigare tra sessioni passate e avviare nuove conversazioni. `useChatApi.js` è stato riconvertito da hook deprecato a hook dedicato per il fetch della history.

- ✅ **Migliorare renderizzazione markdown** `🔵 Miglioramento`
  Le risposte dell'AI sono renderizzate tramite `react-markdown` con il plugin `remark-gfm`. Supporto completo per tabelle, bold, italic, liste ordinate/non-ordinate, blocchi di codice, link e tutti i principali stili GFM per un output leggibile e professionale.

---

## ⚠️ Note Importanti

### `useChatApi.js` — Riabilitato (non più deprecato)
Il file `src/hooks/useChatApi.js` è stato riconvertito da hook non-streaming (deprecato) a hook dedicato al fetch della **chat history** (`fetchChatHistory`). Viene importato da `WorkspaceWrapper` per il restore delle sessioni passate tramite `GET /v1/conversations/{session_id}/messages`.

### `AIReferenceBanner` — Temporaneamente disabilitato
Il componente `AIReferenceBanner.jsx` è stato commentato in `ManualViewer.jsx`. La funzione di mostrare snippet RAG in overlay è risultata ridondante con la navigazione diretta alla pagina tramite citation. Può essere riabilitato decommentando il relativo blocco in `ManualViewer.jsx`.

### `machine_id` senza autenticazione
Il `machine_id` viene estratto direttamente da `useParams()` (URL). Chiunque conosca un ID può accedere ai dati di quella macchina — non c'è verifica di autenticazione.

---

## 📋 To-Do

- [ ] **#1 — Aggiornare sezione frontend del README generale del workspace**

- [ ] **#2 — Autenticazione `machine_id`** `🔴 Sicurezza`
  Il `machine_id` viene estratto direttamente da `useParams()` (URL). Chiunque conosca un ID può accedere ai dati di quella macchina — non c'è verifica di autenticazione. Aggiungere un meccanismo di verifica (es. token JWT, sessione operatore) prima di caricare i dati di una macchina in `LandingQR` e `WorkspaceWrapper`.
