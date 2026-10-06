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
/login           → LoginPage        (form di autenticazione)
/                → FleetView        (lista flotta macchine) [PROTETTA]
/fleet           → FleetView        (alias)                 [PROTETTA]
/machine/:id     → LandingResolver  → LandingQR (scansione QR + scheda macchina) [SEMI-PUBBLICA]
/workspace/:id   → WorkspaceWrapper → ChatWorkspace (chat SSE + ManualViewer)    [SEMI-PUBBLICA]
/scanner         → MachineScanner   (scansione manuale via fotocamera)            [PROTETTA]
```

**Modello di accesso:**
- **PROTETTA** — richiede autenticazione completa (utente reale); gli utenti guest vengono reindirizzati a `/login`.
- **SEMI-PUBBLICA** — la pagina macchina e il manuale PDF sono sempre accessibili; la chat AI richiede login reale (il gate è mostrato inline nella workspace).

### State Management

```
AuthProvider (React Context globale — AuthContext.jsx)
    ├── user            → { user_id, company_id, first_name, last_name, email, visibility, is_guest }
    ├── isAuthenticated → !!user
    ├── authLoading     → true durante la risoluzione della sessione al mount
    ├── login()         → POST /v1/sessions  { email, password }  → Set-Cookie: arol_session
    ├── loginAsGuest()  → POST /v1/sessions  { email: "guest", password: guest_token }
    │                     (mock: lookup in MOCK_GUEST_TOKENS; real: endpoint backend)
    └── logout()        → DELETE /v1/sessions/current  → clearSessionStorage

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
│   │       ├── MOCK_USERS.js          # Utenti mock + MOCK_GUEST_TOKENS (un token per company)
│   │       ├── MOCK_FLEET.jsx         # Dataset macchine mock con company_id
│   │       ├── MOCK_MANUALS.jsx       # Associazione machine → manuale mock
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
│   │       ├── Header.jsx             # Header generico condiviso
│   │       └── ProtectedRoute.jsx     # Guard route: blocca utenti non autenticati e guest
│   ├── context/
│   │   ├── AuthContext.jsx            # Provider auth: login, loginAsGuest, logout, sessione persistente
│   │   └── MachineContext.jsx         # Provider flotta: fetch, scan, cache, offline fallback
│   ├── hooks/
│   │   ├── useChatStream.js           # Hook SSE streaming (fetch + ReadableStream) — principale
│   │   └── useChatApi.js              # Hook REST: fetchChatHistory per restore conversazioni
│   ├── models/
│   │   └── ChatMessage.js             # Schema ChatMessage con DEFAULT_CHAT_MESSAGE
│   ├── pages/
│   │   ├── LoginPage.jsx              # Pagina login con form email/password
│   │   ├── FleetView.jsx              # Dashboard flotta: griglia macchine, filtri, ricerca
│   │   ├── LandingQR.jsx              # Landing post-scansione: scheda macchina + navigazione
│   │   ├── LandingResolver.jsx        # Resolver route /machine/:id → LandingQR + guest auto-login
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
│   ├── App.jsx                        # Router React + AuthProvider + MachineProvider
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

- ✅ **Sistema di Autenticazione completo** `🔴 Sicurezza`
  Implementato il layer di autenticazione basato su sessioni server-side con cookie `httpOnly`. `AuthContext.jsx` gestisce l'intero ciclo di vita: `login()` (POST `/v1/sessions`), `logout()` (DELETE `/v1/sessions/current`), e il ripristino della sessione al mount (`GET /v1/sessions/current`). La sessione è mantenuta in un cookie `arol_session` opaco — nessun token nel frontend. `sessionStorage` è usato solo come cache di visualizzazione rapida (evita il flash UI al refresh), con il server come unica source of truth.

- ✅ **Login automatico Guest via QR code** `🔵 Funzionalità`
  Il QR code di ogni macchina può ora incorporare un `?guest_token=<token>` nell'URL. Quando `LandingResolver` rileva il parametro, chiama `loginAsGuest()` che autentica automaticamente l'utente come ospite dell'azienda proprietaria del macchinario. Il guest vede la scheda macchina e il manuale PDF, ma la chat AI è bloccata da un gate inline che richiede login con credenziali reali. In mock mode i token sono definiti in `MOCK_GUEST_TOKENS` (in `MOCK_USERS.js`); in real mode viene chiamato il backend.

  **URL QR per test (mock mode):**
  ```
  http://localhost:3000/machine/001?guest_token=mock-guest-cmp001-beccaris
  http://localhost:3000/machine/003?guest_token=mock-guest-cmp002-nuoro
  ```

- ✅ **Modello di visibilità a tre livelli** `🔵 Funzionalità`
  Le route sono ora classificate in tre livelli di accesso:
  - **Protette** (`/`, `/fleet`, `/scanner`): richiedono autenticazione reale; gli utenti guest vengono reindirizzati a `/login` da `ProtectedRoute.jsx`.
  - **Semi-pubbliche** (`/machine/:id`, `/workspace/:id`): la scheda macchina e il PDF sono sempre visibili; la chat AI richiede login reale (gate inline in `WorkspaceWrapper`).
  - **Pubbliche** (`/login`): accessibili senza autenticazione.
  Dopo login reale da guest, il cookie viene sovrascritto e l'utente è identificato come utente specifico; la chat si sblocca automaticamente.

- ✅ **Fix parser SSE: thinking non appare più nella risposta** `🐛 Bug Fix`
  Il parser SSE in `useChatStream.js` inizializzava `eventType` a `'message'` invece di `null`. Questo causava che frame `thinking` senza riga `event:` esplicita (o con tipo non riconosciuto) venissero instradati nel `default` del `switch`, che chiamava `onToken()` — rendendo il testo del ragionamento interno visibile nella bolla di risposta. Fix: `eventType` inizia a `null`; il `default` ora logga un warning senza toccare `onToken`. Corretta anche la concatenazione dei campi `data:` multi-riga per conformità alla spec SSE.

- ✅ **Fix stale machine: navigare a ID diverso ora mostra errore corretto** `🐛 Bug Fix`
  In `MachineContext.scanMachine()`, quando si richiedeva un ID diverso da quello già in cache, `activeMachine` manteneva il valore vecchio durante il fetch asincrono. `LandingQR` vedeva l'`activeMachine` non-null e scattava `onScanSuccess` (redirect al workspace) prima che arrivasse l'errore. Fix: `activeMachine` viene azzerato a `null` immediatamente se l'ID richiesto è diverso da quello corrente.

- ✅ **Toggle "AI Thinking" espandibile** `🔵 Miglioramento`
  Quando l'AI invia eventi `thinking` (ragionamento interno del modello), viene mostrato un elemento collassabile nella bolla AI — un accordion `💭 Mostra ragionamento` — che l'operatore può espandere per vedere il processo decisionale dell'AI. Implementato in `ChatBubble.jsx` tramite il campo `thinkingText`, accumulato da `WorkspaceWrapper` via callback `onThinking` dall'hook `useChatStream`.

- ✅ **Drawer ricerca testo nel PDF** `🟡 UX`
  Il `SearchDrawer.jsx` è ora collegato alla logica di ricerca full-text nel `ManualViewer`. All'apertura di ogni PDF, il testo viene estratto pagina per pagina con `react-pdf` (`getTextContent()`). La ricerca avviene client-side: supporta sia la ricerca per titolo/filename tra tutti i manuali disponibili, sia la ricerca full-text nel documento aperto, con navigazione diretta alla pagina del match.

- ✅ **Implementazione frontend Chat History**
  Gestione completa della cronologia delle conversazioni per macchina. Le sessioni sono salvate in `localStorage` (`arol_sessions_{machineId}`). All'init, `WorkspaceWrapper` carica automaticamente l'ultima sessione dal backend via `GET /v1/conversations/{session_id}/messages`, ricostruendo la cronologia con i rispettivi messaggi e citazioni. Il componente `ChatHistoryDrawer` permette di navigare tra sessioni passate e avviare nuove conversazioni.

- ✅ **Rendering Markdown GFM completo** `🔵 Miglioramento`
  Le risposte dell'AI sono renderizzate tramite `react-markdown` con il plugin `remark-gfm`. Supporto completo per tabelle, bold, italic, liste ordinate/non-ordinate, blocchi di codice, link e tutti i principali stili GFM.

---

## ⚠️ Note Importanti

### Sessione guest e refresh
Il flag `is_guest` viene impostato dal frontend in `loginAsGuest()` e salvato in `sessionStorage`. Al refresh, la sessione viene rivalidata con `GET /v1/sessions/current`: se il backend non include `is_guest` nel `UserOut`, il flag si perde e il guest appare come utente normale (chat sbloccata). Per una protezione robusta, aggiungere `is_guest: bool` al modello `User` e `UserOut` nel backend (vedi Opzione A nella documentazione backend).

### Lista sessioni salvata in localStorage
I `thread_id` delle conversazioni sono salvati in `localStorage` (`arol_sessions_{machineId}`). Non esiste un endpoint backend per elencarle (`GET /v1/conversations` non è implementato). Cambiare browser o dispositivo comporta la perdita della lista, anche se i messaggi rimangono recuperabili lato server con il thread_id.

### `AIReferenceBanner` — Temporaneamente disabilitato
Il componente `AIReferenceBanner.jsx` è stato commentato in `ManualViewer.jsx`. La funzione di mostrare snippet RAG in overlay è risultata ridondante con la navigazione diretta alla pagina tramite citation. Può essere riabilitato decommentando il relativo blocco in `ManualViewer.jsx`.

