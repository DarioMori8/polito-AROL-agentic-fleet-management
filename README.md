# Polito x AROL - Agentic Fleet Management

Piattaforma conversazionale che assiste gli operatori di stabilimento tramite un
insieme di agenti specializzati: documentazione tecnica delle macchine, dati
commerciali, telemetria, allarmi e manutenzione.

## Servizi

| Servizio | Porta | Cosa fa |
|---|---|---|
| `frontend` | 8080 | UI operatore (scansione QR, chat, viewer manuali) |
| `backend` | 8000 | API, orchestratore LangGraph, anagrafica macchine |
| `agents` | 8001 | Manuals Agent, Docs Agent e IoT Agent |
| `mock-backoffice` | 8003 | Sta al posto dell'ERP/CRM: preventivi, ordini, documenti |
| `langfuse-web` | 3000 | Tracing delle esecuzioni dell'orchestratore |

Langfuse arriva da `langfuse-local/docker-compose.yml`, incluso dal compose
principale: tira su anche postgres, clickhouse, redis e minio, quindi il primo
avvio è lento.

---

# Avvio con Docker Compose

Questi sono gli step minimi per far partire tutto. I dettagli specifici di ogni
servizio stanno nelle sezioni più sotto.

## 1. Prerequisiti

- Docker e Docker Compose (`docker compose version` deve rispondere)
- **Ollama acceso sull'host**, con i modelli `gpt-oss:20b` e `nomic-embed-text`
  già scaricati

Ollama **non** è un servizio del compose: i container lo raggiungono sull'host
tramite `host.docker.internal:11434`, quindi deve essere già in esecuzione prima
di avviare lo stack.

> Se non l'hai mai installato, o se ti mancano i modelli, fai prima gli step
> **1, 2 e 3** di [`agents/README.md`](agents/README.md) — installazione,
> download dei due modelli e verifica — e poi torna qui. Non sono ripetuti in
> questa pagina per non tenere due copie delle stesse istruzioni.

### Avviare Ollama

- **macOS**: parte da solo aprendo l'app. Se l'hai installato con Homebrew:
  `brew services start ollama`
- **Linux**: l'installer registra un servizio systemd, quindi
  `sudo systemctl start ollama`. In alternativa `ollama serve` in un terminale
  dedicato, da lasciare aperto
- **Windows**: parte automaticamente come servizio in background dopo
  l'installazione (icona nella system tray)

Verifica che risponda e che entrambi i modelli siano elencati:

```bash
curl http://localhost:11434/api/tags
```

## 2. File di ambiente

Prima di avviare servono due file, nessuno dei due versionato:

- **`.env` nella radice del repository**, con le chiavi Langfuse. Il compose si
  ferma subito senza, perché le referenzia come obbligatorie:

  ```dotenv
  LANGFUSE_PUBLIC_KEY=pk-lf-...
  LANGFUSE_SECRET_KEY=sk-lf-...
  ```

- **`langfuse-local/.env`**, con i segreti dell'istanza Langfuse. La procedura
  per generarli è in [`langfuse-local/README`](langfuse-local/README).

Gli altri servizi hanno i propri `.env`: vedi le rispettive sezioni.

## 3. Avviare

```bash
docker compose up --build
```

L'ordine è gestito dagli healthcheck: `mock-backoffice` per primo, poi `agents`,
poi `backend`, infine `frontend`.

## 4. Verificare

Il `mock-backoffice` costruisce il proprio database dal workbook Excel al primo
avvio, da solo: non serve lanciare nulla. I dettagli sono nella sezione
[Mock-backoffice](#mock-backoffice).

```bash
docker compose ps
```

Tutti i servizi devono risultare `healthy` o `running`. In caso di dubbi:

```bash
curl http://localhost:8003/health
curl http://localhost:8001/health
curl http://localhost:8000/health
```

Ognuno deve rispondere `{"status":"ok"}`. Il frontend è su
[localhost:8080](http://localhost:8080), Langfuse su
[localhost:3000](http://localhost:3000).

> Attenzione: i container possono risultare `healthy` anche se Ollama non è
> raggiungibile — l'healthcheck non lo verifica. In quel caso partono tutti
> correttamente ma ogni domanda in chat fallisce a runtime.

---

# Agents

Il container `agents` parte da solo, ma il Manuals Agent non risponde finché non
gli metti i manuali e non fai l'ingestion. Sono due step manuali, una tantum.

## 1. Mettere i manuali in `data/manuals/`

I manuali **non sono nel repository**: sono proprietà di AROL, forniti per il
solo uso didattico. Vanno scaricati dal pacchetto dataset del corso (la cartella
`manuals/`, insieme a `AROL_Q2_synthetic_fleet_dataset.xlsx`) e copiati in
`data/manuals/` alla radice del repository:

```
data/manuals/
├── 15610_manual_EN.pdf
├── 17203_manual_EN.pdf
├── 17478_manual_EN.pdf
├── 17579_manual_EN.pdf
├── A2055_manual_EN.pdf
├── A2064_manual_EN.pdf
├── A2132_manual_EN.pdf
└── A4344_manual_EN.pdf
```

Il compose monta questa cartella in sola lettura su `/data/manuals` dentro il
container, quindi basta copiarceli dentro: non serve ricostruire l'immagine.

Il nome del file conta: contiene il **serial number** della macchina. L'ingestion
lo traduce nel `machineId` corrispondente (`17478_manual_EN.pdf` → `17478` →
`MCH-0004`) chiedendolo al registro della flotta del `mock-backoffice`, e usa
quello nei metadati di ogni chunk. È la chiave con cui l'agente, a runtime, cerca
solo dentro il manuale della macchina giusta — e il motivo per cui tutto il
sistema, dal QR fino a Chroma, usa un identificativo solo. I file che non seguono
lo schema `<serialNumber>_manual_<LANG>.pdf` vengono saltati con un messaggio.

> `data/` è in `.gitignore`, quindi i PDF non finiscono mai in un commit.

## 2. Fare l'ingestion

L'agente non legge i PDF al volo: cerca in un database vettoriale (Chroma). Va
quindi popolato una volta sola, a container acceso:

```bash
docker compose exec agents python -m manuals_agent.ingestion
```

Output atteso la prima volta:

```
Ingested 15610_manual_EN.pdf -> MCH-0001: 277 chunk
Ingested 17203_manual_EN.pdf -> MCH-0002: 263 chunk
...
```

Il `mock-backoffice` deve essere in piedi — con Compose lo è già, `agents` non
parte prima che sia `healthy` — perché è lui a dire quale `machineId` corrisponde
a ciascun serial.

**Mettici in conto parecchi minuti**: sono 2155 chunk in totale e ognuno richiede
una chiamata di embedding a Ollama. Lascialo finire.

L'indice finisce in `agents/data/chroma/`, che è dentro il bind mount del
codice, quindi **sopravvive** a `docker compose down` e ai rebuild. L'ingestion
si fa una volta sola.

Lo script è idempotente per singolo manuale: rilanciandolo, quelli già
indicizzati vengono saltati e viene ingerito solo ciò che manca.

```
Already ingested 15610_manual_EN.pdf
```

Quindi se aggiungi un nono PDF ti basta rilanciare il comando. Per forzare un
re-ingestion completo, cancella `agents/data/chroma/` e rilancia — serve per
esempio se cambi il modello di embedding, perché vettori calcolati con modelli
diversi non sono confrontabili.

## 3. Verificare che risponda

```bash
curl -X POST http://localhost:8001/agents/manuals/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What safety precautions should be taken before maintenance?", "machine_id": "MCH-0004"}'
```

`machine_id` è quello del dataset, da `MCH-0001` a `MCH-0008`. Se la risposta
contiene `citations` con `doc` e `page` reali, il RAG funziona.

Se `citations` è vuoto e `confidence` è `0.0`: o l'ingestion non è stata fatta,
o il `machine_id` non corrisponde a nessun manuale indicizzato.

## Per lo sviluppo in locale

Per lavorare sugli agenti fuori da Docker (venv, uvicorn, test dei tre agenti
uno per uno) la guida completa è in [`agents/README.md`](agents/README.md).

---

# Backend

_TODO_

# Frontend

Mobile-first **Progressive Web Application (PWA)** costruita con React 19 + Vite 8, ottimizzata per tecnici di stabilimento su dispositivi rugged. La UI segue il design system **AROL Rugged UI** (touch target ≥ 48 px, alto contrasto, design token in `tokens.css`).

La documentazione completa del frontend — architettura, design system, flusso SSE e struttura del progetto — è in [`frontend/README.md`](frontend/README.md).

## Tech stack principale

| Layer | Libreria |
| :--- | :--- |
| Framework | React 19 + Vite 8 |
| Routing | React Router v8 |
| PWA | `vite-plugin-pwa` (manifest + service worker) |
| PDF Viewer | `react-pdf` v10 |
| Markdown | `react-markdown` + `remark-gfm` |
| QR Scanner | `html5-qrcode` |
| Produzione | Nginx Alpine (multi-stage Dockerfile) |

## Features principali

- **Chat AI in streaming** — SSE token-by-token via `POST /v1/chat/stream`; parsing di eventi `start`, `thinking`, `token`, `citations`, `done`, `error`
- **AI Thinking accordion** — il ragionamento interno del modello (`thinking` events) è mostrato in un pannello collassabile `💭 Mostra ragionamento` nelle bolle AI
- **Viewer PDF integrato** — navigazione pagine, zoom, fullscreen, citation routing (click sulla citazione → pagina esatta del manuale)
- **Ricerca full-text nel PDF** — testo estratto client-side con `react-pdf` e ricercato in real-time con navigazione ai match
- **Chat History** — sessioni per macchina salvate in `localStorage`; restore automatico dell'ultima sessione dal backend (`GET /v1/conversations/{session_id}/messages`); `ChatHistoryDrawer` per navigare le conversazioni passate
- **Rendering Markdown GFM** — risposte AI con tabelle, bold, code block, liste via `react-markdown` + `remark-gfm`
- **QR Scanner** — scansione QR code delle macchine via fotocamera (`html5-qrcode`)
- **Offline/mock mode** — `VITE_USE_MOCK=true` attiva la simulazione SSE locale senza backend

## Routes

| Percorso | Componente | Descrizione |
| :--- | :--- | :--- |
| `/` o `/fleet` | `FleetView` | Dashboard flotta con griglia macchine e filtri |
| `/machine/:id` | `LandingQR` | Scheda macchina post-scansione QR |
| `/workspace/:id` | `WorkspaceWrapper` | Chat AI + viewer manuali |
| `/scanner` | `MachineScanner` | Scanner QR via fotocamera |

## Come avviare

```bash
cd frontend
cp .env.example .env       # configura VITE_API_URL (default: http://localhost:8000)
npm install
npm run dev                # → http://localhost:3000
```

In Docker (stack completo) il frontend è raggiungibile su `http://localhost:8080`.

# Mock-backoffice

Sta al posto dell'ERP/CRM reale di AROL e serve i dati del dataset Q2: aziende,
macchine, preventivi con lo storico revisioni, ordini, telemetria e allarmi.

## Non c'è niente da fare

Il database **si costruisce da solo** al primo avvio del container. Il servizio
legge `mock-backoffice/dataset/AROL_Q2_synthetic_fleet_dataset.xlsx` e scrive
`mock-backoffice/data/backoffice.db` prima di iniziare a servire richieste.

Nel repository c'è il **workbook**, non il database: il `.db` è dato derivato e
si rigenera in meno di un secondo, quindi versionarlo sarebbe solo un binario in
più da tenere allineato. Nei log del container, al primo avvio:

```
Companies                   5 righe, 7 colonne
...
TelemetrySnapshots       5760 righe, 10 colonne

Scritto data/backoffice.db (988 KB)
```

Viene ricostruito **solo** se manca o se il workbook è più recente, quindi i
riavvii successivi non ripetono il lavoro.

## Se il dataset viene aggiornato

Sostituisci il file in `mock-backoffice/dataset/` e riavvia il servizio: il
timestamp più recente basta a farlo ricaricare da zero.

```bash
docker compose restart mock-backoffice
```

Per forzare la ricostruzione senza toccare il workbook, cancella il database:

```bash
rm mock-backoffice/data/backoffice.db && docker compose restart mock-backoffice
```

## Verificare

```bash
curl http://localhost:8003/health
curl http://localhost:8003/machines
```

Il primo deve rispondere `{"status":"ok"}`, il secondo elencare le 8 macchine
della flotta con serial number, modello e azienda proprietaria.

Se ottieni **`503 Dataset not loaded`**, il workbook non è dove il servizio se lo
aspetta: il servizio parte comunque — così un dataset mancante non blocca tutto
lo stack — ma non ha dati da servire.

## Endpoint disponibili

| Endpoint | Cosa restituisce |
|---|---|
| `GET /machines` | la flotta, con serial, modello e azienda |
| `GET /machines/{machine_id}` | dettaglio macchina, configurazione as-built e specifiche del modello |
| `GET /machines/{machine_id}/health` | sintesi operativa su una finestra temporale: uptime, produzione, temperatura, allarmi ricorrenti |
| `GET /machines/{machine_id}/telemetry` | ricerca limitata degli snapshot IoT con filtri temporali e di stato |
| `GET /machines/{machine_id}/alarms` | ricerca degli eventi di allarme per data, severità, stato o codice |
| `GET /machines/{machine_id}/maintenance-tickets` | ricerca dei ticket per data, stato, priorità o allarme collegato |
| `GET /companies/{company_id}/orders` | ordini del cliente, con le righe e il totale della revisione approvata |
| `GET /companies/{company_id}/quotes` | preventivi del cliente, con lo storico revisioni, stato e importo correnti |

I due endpoint commerciali accettano `?machine_id=` per restringere a una singola
macchina, più i filtri `status`, `order_id` e `quote_id`.

Sono scopati per **azienda** e non per macchina perché è così che sono fatti i
dati: un ordine porta un `companyId`, e arriva a una macchina solo attraverso le
righe di una revisione di preventivo — quando ci arriva, perché un preventivo per
una macchina non ancora installata non punta a nessuna macchina.
