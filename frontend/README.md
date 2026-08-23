# AROL Multi-Agent Conversational Ecosystem — Frontend Client

Mobile-first Progressive Web Application (PWA) per tecnici di manutenzione e operatori di stabilimento industriale. Costruita sul design language **AROL Rugged UI**, ottimizzata per visibilità ad alto contrasto e interazioni touch con guanti su dispositivi rugged (smartphone, tablet, PMA industriali).

Il frontend è l'interfaccia utente dell'ecosistema conversazionale AROL: permette di scansionare QR code delle macchine, consultare un troubleshooter AI multi-agente, ricevere risposte in streaming SSE token-by-token, e visualizzare i segmenti di manuale recuperati dal RAG (ChromaDB) nel viewer PDF integrato.

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
| **PDF Viewer** | `react-pdf` | Visualizzatore manuali tecnici AROL |
| **Testing** | Vitest + Playwright | Test Storybook via `@storybook/addon-vitest` |
| **Component Docs** | Storybook 10 | Dev server su porta `6006` |
| **Production Server** | Nginx (Alpine) | SPA fallback con `try_files $uri /index.html` |

### Configurazioni Chiave
- **Path Alias**: `@` → `src/` (es. `import Button from '@/components/ui/Button'`)
- **Dev Server**: porta `3000`, `host: true` — esposto in LAN per test su dispositivi fisici
- **PWA Display**: `standalone`, orientamento `portrait`, tema `#002D54` (blu AROL)

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
    ├── useChatStream()   → hook SSE streaming
    └── sessionStorage    → arol_session_id_{machineId}  (continuità conversazionale)
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
        ├── "start"     → acquisisce session_id
        ├── "thinking"  → (parsato, non ancora mostrato in UI — to-do #3)
        ├── "token"     → onToken() → aggiorna bolla AI carattere per carattere
        ├── "status"    → (parsato, non ancora mostrato in UI — to-do #3)
        ├── "citations" → onComplete() con citations[]
        ├── "error"     → onError()
        └── "done"      → salva session_id in sessionStorage
```

---

## 📂 Struttura del Progetto

```
frontend/
├── public/
│   └── icons/                         # Icone PWA (192x192, 512x512)
├── src/
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatBubble.jsx         # Bolla chat: testo, citazioni, errori, retry
│   │   │   ├── ChatInput.jsx          # Input bar con gestione invio e stato loading
│   │   │   ├── ChatWindow.jsx         # Feed chat: lista bolle + suggestion chips
│   │   │   ├── ChatWindowHeader.jsx   # Header workspace con info macchina attiva
│   │   │   └── SuggestionChips.jsx    # Chip con domande suggerite contestuali
│   │   ├── manuals/
│   │   │   ├── ManualViewer.jsx       # Viewer PDF con zoom, navigazione pagine, citation routing
│   │   │   ├── AIReferenceBanner.jsx  # Banner snippet RAG sovrapposto al documento
│   │   │   ├── DocumentArea.jsx       # Area rendering documento PDF
│   │   │   ├── SearchDrawer.jsx       # Drawer ricerca parole chiave nel manuale
│   │   │   └── TopToolbar.jsx         # Toolbar viewer: selezione documento, zoom, fullscreen
│   │   └── ui/
│   │       ├── Button.jsx             # Componente bottone riusabile
│   │       └── Header.jsx             # Header generico condiviso
│   ├── context/
│   │   └── MachineContext.jsx         # Provider flotta: fetch, scan, cache, offline fallback
│   ├── hooks/
│   │   ├── useChatStream.js           # Hook SSE streaming (fetch + ReadableStream)
│   │   └── useChatApi.js              # Hook non-streaming (deprecato, non usato)
│   ├── models/
│   │   └── ChatMessage.js             # Schema ChatMessage con DEFAULT_CHAT_MESSAGE
│   ├── pages/
│   │   ├── FleetView.jsx              # Dashboard flotta: griglia macchine, filtri, ricerca
│   │   ├── LandingQR.jsx              # Landing post-scansione: scheda macchina + navigazione
│   │   ├── LandingResolver.jsx        # Resolver route /machine/:id → LandingQR
│   │   ├── MachineScanner.jsx         # Scanner QR via fotocamera (html5-qrcode)
│   │   ├── ChatWorkspace.jsx          # Layout workspace: tab mobile / split-screen tablet
│   │   └── WorkspaceWrapper.jsx       # Orchestratore chat: state messaggi + useChatStream
│   ├── stories/                       # Storybook stories per i componenti
│   ├── styles/
│   │   ├── tokens.css                 # ⭐ Design tokens: colori, spacing, radius, font
│   │   ├── base.css                   # Reset CSS globale
│   │   ├── index.css                  # Entry point CSS
│   │   ├── App.css                    # Stili viewport globali
│   │   ├── ChatBubble.css
│   │   ├── ChatInput.css
│   │   ├── ChatWindow.css
│   │   ├── ChatWorkspace.css
│   │   ├── FleetView.css
│   │   ├── LandingQR.css
│   │   ├── ManualViewer.css
│   │   └── ...                        # Un file CSS per ogni componente
│   ├── App.jsx                        # Router React + MachineProvider
│   └── main.jsx                       # Entry point React
├── .env                               # VITE_API_URL (non versionato)
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

## ⚠️ Note Importanti

### `useChatApi.js` — Deprecato
Il file `src/hooks/useChatApi.js` è la vecchia implementazione non-streaming. **Non è usato** nel workspace principale (sostituito da `useChatStream.js`). Contiene anche un'incongruenza: invia `{ message: ... }` mentre il backend si aspetta `{ query: ... }`. Mantenuto solo come riferimento, da ignorare.

### `machine_id` senza autenticazione
Il `machine_id` viene estratto direttamente da `useParams()` (URL). Chiunque conosca un ID può accedere ai dati di quella macchina — non c'è verifica di autenticazione.

---

## 📋 To-Do

- [x] **#1 — Cursore animato durante lo streaming** `🟡 UX`
  La bolla AI è vuota/invisibile prima che arrivi il primo token. Aggiungere un cursore lampeggiante (`▍`) in `ChatBubble.jsx` quando `status === 'sending'` e `text === ''`.
  ```jsx
  const displayText = status === 'sending' && !text ? '▍' : text;
  ```

- [x] **#2 — Allineamento `id` placeholder / `finalMessage`** `🟠 Fragile`
  Il placeholder AI creato in `WorkspaceWrapper` ha id `ai-stream-*`, ma il `finalMessage` costruito da `useChatStream.js` genera un nuovo id `ai-*`. La sostituzione via `prev.map()` funziona ma è fragile. Riusare l'`aiMessageId` originale anche nel `finalMessage`.

- [x] **#3 — Test decodifica QR in `MachineScanner`** `🟠 Testing`
  Verificare end-to-end che `MachineScanner.jsx` (che usa `html5-qrcode`) decodifichi correttamente il QR code di una macchina e navighi verso `/machine/:id`. Aggiungere test Playwright che simuli la scansione (o mocki il risultato del decoder) per coprire il flusso completo QR → landing.

- [x] **#4 — Highlight citazioni AI direttamente sul testo PDF** `🔵 Miglioramento`
  Quando l'AI restituisce una citazione (`{ doc, page, snippet }`), evidenziare il testo corrispondente direttamente nella pagina PDF nel `ManualViewer`. Attualmente viene mostrato solo il banner `AIReferenceBanner` con lo snippet. Usare le API di `react-pdf` per cercare e selezionare visivamente il testo nella pagina indicata.

- [x] **#5 — Toggle "AI Thinking" espandibile** `🔵 Miglioramento`
  Quando l'AI invia eventi `thinking` (ragionamento interno del modello), mostrare un elemento collassabile nella bolla AI — es. un accordeon `💭 Mostra ragionamento` — che l'operatore può espandere per vedere il processo decisionale dell'AI. Utile per debug e per la fiducia nel sistema.

- [x] **#6 — Drawer ricerca testo nel PDF** `🟡 UX`
  Il componente `SearchDrawer.jsx` esiste già ma va collegato alla logica di ricerca testuale nel `ManualViewer`. Implementare la ricerca full-text nelle pagine del documento aperto usando le API di `react-pdf`, con highlight dei risultati e navigazione tra occorrenze (prev/next).

- [x] **#7 - Implementazione frontend Chat History (local storage)**
  Il backend è stato costruito per poter riprendere le conversazioni passate, salvandole su un database SQLite.

  Backend route (chat.py): GET /v1/conversations/{session_id}/messages
  Risultato: Restituisce l'oggetto ConversationHistory che mappa l'intero storico (utente e assistente) con eventuali citazioni dei manuali allegate.

- [ ] **#8 - Migliorare renderizzazione markdown**
  Aggiungere la visualizzazione di tabelle, stili markdown principali, ecc... per un output più leggibile e user-friendly.

- [ ] **#9 — Aggiornare sezione frontend del README generale del workspace**

- [ ] **#10 — Autenticazione `machine_id`** `🔴 Sicurezza`
  Il `machine_id` viene estratto direttamente da `useParams()` (URL). Chiunque conosca un ID può accedere ai dati di quella macchina — non c'è verifica di autenticazione. Aggiungere un meccanismo di verifica (es. token JWT, sessione operatore) prima di caricare i dati di una macchina in `LandingQR` e `WorkspaceWrapper`.
