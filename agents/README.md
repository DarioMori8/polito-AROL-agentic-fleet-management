# Agents

Questo servizio contiene **tre agenti**, tutti esposti come endpoint HTTP:

| Agente | Endpoint | A cosa risponde | Fonte dati |
|---|---|---|---|
| **Manuals Agent** | `POST /agents/manuals/search` | Domande sul manuale tecnico della macchina | PDF indicizzati in Chroma (locale) |
| **Docs Agent** | `POST /agents/docs/search` | Domande su preventivi, ordini e documenti contrattuali | servizio `mock-backoffice` via HTTP |
| **IoT Agent** | `POST /agents/iot/search` | Telemetria, stato operativo, allarmi e ticket di manutenzione | servizio `mock-backoffice` via HTTP |

Il `mock-backoffice` serve a tutti: Docs e IoT lo interrogano a ogni domanda; il Manuals Agent lo usa durante l'ingestion per risolvere il serial number nel `machineId`.

## Prerequisiti

- Git installato
- Python 3.12 installato
- (Opzionale ma consigliata) GPU NVIDIA con driver aggiornati — verifica con:

  ```bash
  nvidia-smi
  ```

  Deve mostrare la scheda video e la VRAM disponibile. Se il comando non esiste o dà errore, i modelli gireranno su CPU (più lento ma funziona comunque).

## 1. Installare Ollama

**Windows**: scarica l'installer da [ollama.com/download](https://ollama.com/download) ed eseguilo. Ollama parte automaticamente come servizio in background dopo l'installazione (icona nella system tray).

**Linux**:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

## 2. Scaricare i modelli

Servono **due** modelli distinti: uno per generare le risposte (chat), uno per trasformare il testo in vettori per la ricerca semantica (embedding). Non sono intercambiabili.

```bash
ollama pull gpt-oss:20b
ollama pull nomic-embed-text
```

> **Attenzione**: `gpt-oss:20b` sono ~13.8 GB di download. Se la tua GPU ha meno di ~16GB di VRAM, il modello potrebbe non starci tutto — Ollama farà offload parziale su CPU (più lento ma funzionante). `nomic-embed-text` è molto più leggero (~274 MB).
>
> Alternativa più leggera per il modello di chat:
> ```bash
> ollama pull llama3.1:8b (~5GB)
> ```
> (in tal caso ricordati di cambiare `OLLAMA_MODEL` nel `.env` al punto 6)

## 3. Verificare che Ollama funzioni

```bash
ollama run gpt-oss:20b "ciao, rispondi con una sola parola"
```

Dovrebbe rispondere in pochi secondi (con GPU) o fino a un minuto (solo CPU). Poi verifica che l'API sia raggiungibile e che entrambi i modelli siano elencati:

```bash
curl http://localhost:11434/api/tags
```

Deve elencare sia `gpt-oss:20b` che `nomic-embed-text`.

## 4. Entra in agents

```bash
cd polito-AROL-agentic-fleet-management/agents
```

## 5. Creare l'ambiente Python

```bash
python3.12 -m venv .venv
```

Attivare il venv:

- **Windows (PowerShell)**: `.venv\Scripts\Activate.ps1`
- **Linux**: `source .venv/bin/activate`

Installare le dipendenze:

```bash
pip install -r requirements.txt
```

## 6. Configurare l'ambiente

```bash
# Linux:
cp .env.example .env
# Windows (PowerShell):
copy .env.example .env
```

Apri `.env` con un editor di testo e verifica:

```
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss:20b
EMBEDDING_MODEL=nomic-embed-text

MAX_ITERATIONS=5
CHROMA_PATH=./data/chroma
MANUALS_PATH=../data/manuals
DOCS_SERVICE_URL=http://localhost:8003
IOT_SERVICE_URL=http://localhost:8003
```

Se hai scaricato un modello di chat diverso al punto 2, aggiorna `OLLAMA_MODEL` di conseguenza. Gli altri valori puoi lasciarli come sono.

`MANUALS_PATH` è la cartella da cui l'ingestion legge i PDF. Il valore `../data/manuals` vale quando lanci i comandi da dentro `agents/`, come in questa guida; dentro Docker la stessa cartella è montata su `/data/manuals` ed è il compose a passare il valore giusto.

## 7. Scaricare i manuali

I manuali **non sono nel repository**: sono proprietà di AROL, forniti per il solo uso didattico, e non vengono versionati. Vanno scaricati dal pacchetto dataset del corso — è la cartella `manuals/`, quella distribuita insieme a `AROL_Q2_synthetic_fleet_dataset.xlsx` — e copiati in `data/manuals/` **alla radice del repository**, non dentro `agents/`.

```bash
mkdir -p ../data/manuals
# copia qui dentro gli 8 PDF scaricati
```

Al termine `data/manuals/` deve contenere:

```
15610_manual_EN.pdf
17203_manual_EN.pdf
17478_manual_EN.pdf
17579_manual_EN.pdf
A2055_manual_EN.pdf
A2064_manual_EN.pdf
A2132_manual_EN.pdf
A4344_manual_EN.pdf
```

Il nome del file non è decorativo: contiene il **serial number** della macchina (`17478_manual_EN.pdf` → `17478`), che nel dataset è la chiave che lega una macchina al suo manuale. I manuali sono specifici della singola macchina fisica, non del modello: due macchine dello stesso modello hanno manuali diversi e non intercambiabili.

L'ingestion traduce quel serial nel `machineId` corrispondente (`17478` → `MCH-0004`) interrogando il registro della flotta, e usa quello nei metadati dei chunk — così tutto il sistema, dal QR fino a Chroma, parla un identificativo solo. I file il cui nome non segue lo schema `<serialNumber>_manual_<LANG>.pdf` vengono saltati con un messaggio.

> La cartella `data/` è in `.gitignore`, quindi i PDF restano sulla tua macchina e non finiscono mai in un commit.

## 8. Avviare il mock-backoffice

Il `mock-backoffice` sta al posto dell'ERP/CRM reale di AROL e serve i dati del dataset Q2: aziende, macchine, preventivi, ordini, telemetria e allarmi.

**Serve a entrambi gli agenti**, non solo al Docs Agent. Il Manuals Agent lo interroga durante l'ingestion dello step 9, per sapere a quale `machineId` corrisponde il serial number che compare nel nome di ogni PDF: quella corrispondenza esiste solo nel registro della flotta.

Va avviato **in un terminale separato**, e ha un suo venv indipendente da quello di `agents`.

```bash
cd ../mock-backoffice
python3.12 -m venv .venv
```

Attiva il venv (`.venv\Scripts\Activate.ps1` su Windows, `source .venv/bin/activate` su Linux), poi:

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8003
```

**Il database si costruisce da solo all'avvio**: non c'è nessun comando da lanciare. Il servizio legge `mock-backoffice/dataset/AROL_Q2_synthetic_fleet_dataset.xlsx` e scrive `mock-backoffice/data/backoffice.db`. Il workbook è versionato, il `.db` no — è dato derivato. In console vedrai:

```
Companies                   5 righe, 7 colonne
...
TelemetrySnapshots       5760 righe, 10 colonne

Scritto data/backoffice.db (988 KB)
```

Viene ricostruito solo se manca o se il workbook è più recente, quindi i riavvii successivi non ripetono il lavoro. Per forzarlo, cancella `data/backoffice.db` e riavvia, oppure lancia a mano `python load_dataset.py`.

Verifica in un altro terminale:

```bash
curl http://localhost:8003/health
curl http://localhost:8003/machines
```

Il primo deve restituire `{"status":"ok"}`, il secondo le 8 macchine della flotta con serial, modello e azienda. **Lascia questo terminale aperto.**

> Con Docker Compose non serve nulla di tutto questo: il container fa esattamente lo stesso lavoro all'avvio. Basta che il workbook sia al suo posto in `mock-backoffice/dataset/`.

## 9. Popolare il database vettoriale (una tantum, serve solo al Manuals Agent)

Il Manuals Agent risponde cercando nei manuali tramite un database vettoriale (Chroma), non leggendo i PDF al volo. Prima del primo utilizzo va quindi fatta una volta l'**ingestion**: si leggono i PDF da `data/manuals/`, si spezza il testo in porzioni (chunk), si calcola un embedding per ciascuna con `nomic-embed-text`, e si salva tutto in `data/chroma/` (cartella creata automaticamente, non tracciata da git).

```bash
python -m manuals_agent.ingestion
```

> Il `mock-backoffice` dello step 8 deve essere **acceso**: l'ingestion gli chiede
> la corrispondenza fra serial number e `machineId`. Se non risponde, si ferma
> subito invece di indicizzare sotto una chiave sbagliata.

> **Se stai usando Docker Compose** invece del setup locale, gli step 4, 5, 6, 8 e 10 non ti servono — il container ha già il suo ambiente, e `data/manuals/` gli è montata in sola lettura su `/data/manuals`. L'unico step che resta necessario è il 7, mettere i PDF nella cartella. Il comando di ingestion diventa:
>
> ```bash
> docker compose exec agents python -m manuals_agent.ingestion
> ```
>
> Ollama resta comunque sull'host anche in questo caso: il container lo raggiunge su `host.docker.internal:11434`.

Output atteso (la prima volta):

```
Ingested 15610_manual_EN.pdf -> MCH-0001: 277 chunk
Ingested 17203_manual_EN.pdf -> MCH-0002: 263 chunk
Ingested 17478_manual_EN.pdf -> MCH-0004: 495 chunk
Ingested 17579_manual_EN.pdf -> MCH-0003: 252 chunk
Ingested A2055_manual_EN.pdf -> MCH-0007: 201 chunk
Ingested A2064_manual_EN.pdf -> MCH-0006: 222 chunk
Ingested A2132_manual_EN.pdf -> MCH-0008: 171 chunk
Ingested A4344_manual_EN.pdf -> MCH-0005: 274 chunk
```

> **Mettici in conto parecchi minuti.** Sono 2155 chunk in totale e ognuno richiede una chiamata di embedding a Ollama: con GPU sono minuti, su CPU parecchi di più. Lascialo lavorare fino in fondo.

Lo script è idempotente **per singolo manuale**: se lo rilanci, quelli già indicizzati vengono saltati e viene ingerito solo ciò che manca.

```
Already ingested 15610_manual_EN.pdf
```

Questo vuol dire che se aggiungi un nono PDF in `data/manuals/` ti basta rilanciare lo script: verrà ingerito solo quello. E se un'esecuzione si interrompe a metà, rilanciandola riparte da dove si era fermata.

> Per forzare un re-ingestion completo, cancella la cartella `data/chroma/` e rilancia. Serve, per esempio, se cambi `EMBEDDING_MODEL`: embedding calcolati con modelli diversi non sono confrontabili tra loro.

## 10. Avviare il server degli agenti

Torna nel terminale di `agents` (con il suo venv attivo):

```bash
uvicorn main:app --reload --port 8001
```

Output atteso:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8001
```

Se la porta è già occupata, usa `--port 8002` (e aggiorna gli URL sotto di conseguenza).

## 11. Testare il Manuals Agent

1. Apri il browser su `http://localhost:8001/docs`
2. Clicca su **`POST /agents/manuals/search`** per espanderlo
3. Clicca su **"Try it out"**
4. Sostituisci il body con uno di questi esempi. `machine_id` è quello del dataset, da `MCH-0001` a `MCH-0008` (qui `MCH-0004`, la macchina con serial `17478`):

   ```json
   {
     "query": "What safety precautions should be taken before maintenance?",
     "machine_id": "MCH-0004"
   }
   ```

   oppure:

   ```json
   {
     "query": "What should I check on the pneumatic system before repair?",
     "machine_id": "MCH-0004"
   }
   ```

5. Clicca **"Execute"**
6. Attendi la risposta (con `gpt-oss:20b` può richiedere da pochi secondi a circa un minuto, a seconda della GPU) — sotto apparirà "Response body" con `Code: 200`, un `answer` testuale e una lista `citations` con `doc`/`page`/`snippet` presi davvero dal PDF (non inventati)

Se la risposta contiene `citations` con pagine valide del manuale (es. `"page": 120`), il flusso end-to-end funziona correttamente.

## 12. Testare il Docs Agent

Stessa procedura, ma su **`POST /agents/docs/search`**. Il body qui ha due campi identificativi invece di uno:

```json
{
  "query": "Why did the price of quote QTE-2025-0001 change during the negotiation?",
  "company_id": "CMP-001",
  "machine_id": "MCH-0001"
}
```

`company_id` è **obbligatorio** ed è il confine: preventivi e ordini appartengono al cliente, non alla macchina. `machine_id` è facoltativo e serve solo all'agente per restringere, quando la domanda riguarda quella specifica macchina.

Il motivo è nella forma dei dati: un ordine porta un `companyId`, e arriva a una macchina solo attraverso le righe di una revisione del preventivo — quando ci arriva, perché **un preventivo per una macchina non ancora installata non punta a nessuna macchina**. Scopare per macchina renderebbe quei preventivi invisibili per sempre.

La corrispondenza macchina → azienda la trovi con `curl http://localhost:8003/machines`. Per le 8 macchine del dataset:

| macchina | azienda | |  macchina | azienda |
|---|---|---|---|---|
| MCH-0001, MCH-0002, MCH-0003 | CMP-001 | | MCH-0006 | CMP-004 |
| MCH-0004, MCH-0005 | CMP-003 | | MCH-0007, MCH-0008 | CMP-002 |

L'agente ha due tool e **sceglie da solo quale usare**. Prova queste in ordine:

**a) Storico revisioni di un preventivo** — il test più interessante, perché la risposta si costruisce confrontando revisioni successive:

```json
{
  "query": "Why did the price of quote QTE-2025-0001 change during the negotiation?",
  "company_id": "CMP-001",
  "machine_id": "MCH-0001"
}
```

Risposta attesa: da 54.450 a 45.837,50 EUR, per due motivi — retrofit fotocellula tolto dal perimetro e sconto volume del 5%.

**b) Ordini della macchina**

```json
{
  "query": "What orders have been placed for this machine and how much did they cost?",
  "company_id": "CMP-001",
  "machine_id": "MCH-0001"
}
```

Risposta attesa: `ORD-2025-0001`, chiuso e installato, 45.837,50 EUR, con le due righe che lo compongono.

**c) Cosa è ancora in produzione**

```json
{
  "query": "Which of my orders are still in production?",
  "company_id": "CMP-002"
}
```

Risposta attesa: `ORD-2026-0007`. Nota che qui `machine_id` non c'è: la domanda riguarda il cliente, non una macchina.

**d) Il caso limite** — un preventivo che nessuna macchina può raggiungere:

```json
{
  "query": "What quotes have we received?",
  "company_id": "CMP-005"
}
```

Risposta attesa: `QTE-2026-0010`, per una linea nuova. `CMP-005` è l'azienda che nel dataset ha utenti ma **nessuna macchina**: tutte le righe di quel preventivo hanno `machineId` vuoto, perché la macchina non esiste ancora. È irraggiungibile da qualunque scansione di QR, e si trova solo partendo dall'azienda.

### Come leggere la risposta

```json
{
  "answer": "testo della risposta",
  "sources": [ { "kind": "order | quote", "...": "..." } ],
  "confidence": 1.0
}
```

Il campo `kind` dice da quale fonte arriva ogni elemento, così il frontend può renderizzare un ordine come tabella e un preventivo come storico di revisioni. Se `sources` è vuoto e `confidence` è `0.0`, l'agente non ha trovato nulla e te lo dice onestamente invece di inventare (comportamento voluto).

## 13. Testare l'IoT Agent

L'IoT Agent risponde alle domande sui dati operativi di **una macchina**:

- stato e ultimo snapshot disponibile;
- produzione, uptime produttivo, temperatura ed energia;
- distribuzione degli stati operativi in una finestra temporale;
- eventi di allarme, inclusi codice, severità e stato;
- ticket di manutenzione e loro eventuale collegamento a un allarme.

È esposto direttamente dal servizio `agents`:

```text
POST /agents/iot/search
```

Al momento non è registrato nell'orchestratore LangGraph del `backend`: questa
implementazione riguarda solamente `agents`, `mock-backoffice` e i contratti
condivisi. Il backend potrà integrarlo in un secondo momento senza modificare il
contratto HTTP dell'agente.

### I cinque tool

| Tool | Quando viene usato | Endpoint del mock-backoffice |
|---|---|---|
| `analyze_machine_health` | Quadro generale, ultimo stato e KPI su 24 ore, una settimana o un mese | `GET /machines/{machine_id}/health` |
| `search_telemetry` | Letture orarie di un periodo o di uno specifico stato operativo | `GET /machines/{machine_id}/telemetry` |
| `search_alarms` | Allarmi aperti, storici, per severità o per codice | `GET /machines/{machine_id}/alarms` |
| `search_maintenance` | Ticket, attività aperte, priorità, responsabile o ticket legato a un allarme | `GET /machines/{machine_id}/maintenance-tickets` |
| `analyze_alarm_ticket_coverage` | Correla gli allarmi ai ticket e mostra quali sono coperti, quali no, stato, priorità e responsabile | Combina `/alarms` e `/maintenance-tickets` |

La separazione è intenzionale: per una domanda generale l'LLM riceve una
sintesi SQL compatta; le righe dettagliate vengono caricate solamente quando la
domanda le richiede. In questo modo non si inseriscono nel contesto tutte le 720
righe orarie mensili della macchina.

### Come funziona il ciclo interno

L'IoT Agent usa il ciclo comune definito in `core/base_agent.py`:

1. riceve `query` e `machine_id` e costruisce i messaggi system/user;
2. l'LLM sceglie uno o più dei cinque tool in base alla domanda;
3. `IoTAgent._execute_tool()` aggiunge il `machine_id` del task;
4. `core/iot_client.py` traduce la chiamata in una richiesta HTTP al
   mock-backoffice;
5. il risultato strutturato viene aggiunto alla conversazione come messaggio
   `tool`;
6. l'LLM viene richiamato e può fare un'altra ricerca oppure produrre la
   risposta finale.

Il ciclo termina normalmente quando l'LLM restituisce un messaggio senza
`tool_calls`. Non termina automaticamente perché una ricerca è vuota o perché
esiste un valore di confidence: dopo ogni risultato è sempre il modello a
decidere se raffinare la ricerca o rispondere. `MAX_ITERATIONS` rimane solamente
il limite di sicurezza esterno.

Il `machine_id` non compare negli schemi dei tool visibili all'LLM. Viene preso
dal `SearchIoTTask`, quindi il modello può scegliere intervallo e filtri ma non
può cambiare macchina o allargare la ricerca alla flotta.

### Semantica temporale e dei KPI

Il dataset è sintetico e termina il **4 agosto 2026**. Per questo “ultime 24
ore” significa le 24 ore precedenti all'ultimo snapshot disponibile della
macchina, non le 24 ore precedenti all'orologio del server. La risposta include
sempre gli estremi reali della finestra.

Inoltre:

- `uptimePercentage` misura la quota dell'ora trascorsa producendo, non la salute
  generale della macchina;
- `productionRateBph` e uptime sono zero quando la macchina non produce;
- il rate nominale va letto da `Machines.configurationProfile`, perché due
  macchine dello stesso modello possono avere configurazioni diverse;
- `alarmCount` conta gli eventi dell'ora e gli endpoint `/alarms` ne restituiscono
  il dettaglio;
- un ticket può avere `alarm_id = null`: non tutte le manutenzioni nascono da un
  allarme.

### Esempio

```bash
curl -X POST http://localhost:8001/agents/iot/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Quali allarmi aperti ci sono e hanno già un ticket?","machine_id":"MCH-0007"}'
```

Per questa domanda l'agente usa `analyze_alarm_ticket_coverage`, che cerca gli
allarmi con `status = Open`, recupera i ticket della stessa macchina e correla
gli elementi tramite `alarm_id`. La correlazione avviene nel codice, non nel
modello.

La risposta ha questa forma:

```json
{
  "answer": "...",
  "observations": [
    {
      "kind": "alarms",
      "data": {
        "machine_id": "MCH-0007",
        "summary": {
          "with_ticket": 1,
          "without_ticket": 1,
          "ticket_scan_complete": true
        },
        "alarms": [
          {
            "alarm_id": "ALM-0228",
            "has_ticket": true,
            "tickets": [
              {
                "ticket_id": "TKT-0001",
                "status": "Open",
                "priority": "High",
                "owner_role": "Field Service Engineer"
              }
            ]
          }
        ]
      }
    }
  ],
  "confidence": 1.0
}
```

`observations` conserva esattamente gli aggregati e le righe consultate. `kind`
può essere `health`, `telemetry`, `alarms` o `maintenance`. Se nessun tool ha
prodotto dati strutturati, la lista è vuota e `confidence` vale `0.0`.

### Contratti condivisi

I modelli Pydantic sono separati per dominio in `shared/contracts/contracts/`:

```text
manuals.py   SearchManualTask, Citation, SearchManualResponse
docs.py      SearchDocsTask, Order, Quote, Source, SearchDocsResponse
iot.py       SearchIoTTask, IoTObservation, SearchIoTResponse
```

`contracts/__init__.py` li riesporta, quindi il codice applicativo continua a
usare import stabili come `from contracts import SearchIoTTask`. La separazione
evita che il file `manuals.py` diventi il contenitore di contratti appartenenti
a domini commerciali o IoT diversi.

## Troubleshooting

| Problema | Causa probabile |
|---|---|
| `ModuleNotFoundError` all'avvio di uvicorn | Venv non attivato, o `pip install -r requirements.txt` non eseguito (o eseguito prima che venissero aggiunte le dipendenze `chromadb`/`ollama`/`pymupdf` — rilancia il comando) |
| Timeout / risposta molto lenta | Modello troppo pesante per la GPU/VRAM disponibile — prova `llama3.1:8b` |
| `Connection refused` su `localhost:11434` | Ollama non è avviato — su Linux: `ollama serve` in un altro terminale |
| `ValueError: The ollama python package is not installed` | Manca la dipendenza `ollama` (diversa da `ollama` CLI) — `pip install -r requirements.txt` |
| 422 su uno dei due endpoint | Il body non è JSON valido — controlla di usare virgolette dritte `"` e non tipografiche `" "` |
| **Manuals**: risposta senza `citations` / l'agente dice di non trovare l'informazione | Non hai eseguito lo step 9 (ingestion), oppure il `machine_id` non è uno del dataset (`MCH-0001`…`MCH-0008`) |
| **Manuals**: `No pdf found in ...` all'ingestion | I PDF non sono in `data/manuals/` (step 7), o `MANUALS_PATH` nel `.env` punta altrove — da dentro `agents/` deve valere `../data/manuals` |
| **Manuals**: `Skipped <file>: expected <serialNumber>_manual_<LANG>.pdf` | Il file non rispetta la convenzione di nome del dataset: rinominalo, non cambiare lo script |
| **Manuals**: citazioni prese dal manuale di un'altra macchina | Non dovrebbe succedere: la ricerca è filtrata per `machine_id`. Se capita, i chunk sono stati indicizzati da una versione precedente dell'ingestion, che usava il serial o `"generic"` — cancella `data/chroma/` e rifai lo step 9 |
| **Manuals**: `serial ... is not in the fleet registry` all'ingestion | Il serial nel nome del PDF non esiste in `Machines` — controlla che il workbook nel `mock-backoffice` sia quello giusto |
| **Docs / ingestion**: `httpx.ConnectError` su `localhost:8003` | Il `mock-backoffice` non è avviato — vedi step 8, va tenuto acceso in un terminale separato |
| **Docs**: `sources` sempre vuoto e `confidence: 0.0` | `company_id` sbagliato o non corrispondente alla macchina (vedi la tabella nello step 12), oppure `DOCS_SERVICE_URL` punta a una porta sbagliata |
| **Docs**: `422` con `company_id field required` | Il body non ha `company_id`: da questa versione è obbligatorio, `machine_id` da solo non basta più |
| **Backoffice**: `503 Dataset not loaded` | Manca il workbook in `mock-backoffice/dataset/` — il servizio parte lo stesso ma non ha dati da servire |
| **Docs**: `Address already in use` sulla porta 8003 | Un'altra istanza di `mock-backoffice` è già accesa — riusala, oppure chiudila con `pkill -f "uvicorn main:app --port 8003"` |

## Dove sta andando: i manuali passano al backend

L'assetto descritto qui sopra è una tappa intermedia. Oggi i manuali stanno in `data/manuals/`, una cartella che ognuno popola a mano e che gli agents leggono direttamente dal filesystem: va benissimo per lavorare sull'ingestion e sul RAG, ma non regge quando l'applicazione è completa.

Tre requisiti la fanno cadere:

1. **Il frontend deve mostrare i manuali.** Qualcuno deve servire i PDF via HTTP, e quel qualcuno è il backend: è lui che il frontend interroga.
2. **Il dataset impone un controllo di accesso.** Un utente vede i manuali solo delle macchine della propria azienda, e una richiesta fuori scope va rifiutata esplicitamente. Un PDF servito come file statico non permette nessun controllo: chi conosce il nome del file lo scarica. Serve un endpoint che prima guardi chi sta chiedendo.
3. **I manuali si potranno caricare dalla UI.** A quel punto smettono di essere un contenuto fisso e diventano dati che cambiano mentre l'applicazione gira.

L'assetto di destinazione è quindi questo:

- **Il backend possiede i manuali.** Riceve gli upload, salva i PDF, li serve tramite un endpoint che applica il controllo di accesso, ed è l'unico che scrive in quella cartella.
- **Il backend possiede un DB dei metadati**, con una riga per manuale: `machine_id` (che è anche quello che compare nel nome del file), `company_id` per il controllo di accesso, titolo, lingua, numero di pagine e stato dell'indicizzazione. Prende il posto della lista scritta a mano in `app/resources/repository.py`; l'interfaccia `ManualRepository` esiste già apposta, cambia solo l'implementazione.
- **Gli agents mantengono solo Chroma.** Non leggono più una cartella condivisa: quando il backend riceve un manuale nuovo, glielo manda via HTTP su un endpoint di ingestion, e l'agente estrae il testo, calcola gli embedding e indicizza. Il seed iniziale degli otto manuali dovrà passare per la stessa strada, così la pipeline di ingestion resta una sola.

Fino ad allora `MANUALS_PATH` e la cartella condivisa restano il modo con cui si lavora in locale.
