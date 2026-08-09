# Polito x AROL - Agentic Fleet Management

Piattaforma conversazionale che assiste gli operatori di stabilimento tramite un
insieme di agenti specializzati: documentazione tecnica delle macchine, dati
commerciali, e in prospettiva telemetria e allarmi.

## Servizi

| Servizio | Porta | Cosa fa |
|---|---|---|
| `frontend` | 8080 | UI operatore (scansione QR, chat, viewer manuali) |
| `backend` | 8000 | API, orchestratore LangGraph, anagrafica macchine |
| `agents` | 8001 | Manuals Agent (RAG su Chroma) e Docs Agent |
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
- **Ollama installato sull'host**, con i due modelli scaricati

Ollama **non** è un servizio del compose e non viene installato automaticamente:
i container lo raggiungono sull'host tramite `host.docker.internal:11434`. Va
installato da [ollama.com/download](https://ollama.com/download) (su Linux:
`curl -fsSL https://ollama.com/install.sh | sh`), e poi:

```bash
ollama pull gpt-oss:20b
ollama pull nomic-embed-text
```

Sono ~13 GB il primo e ~274 MB il secondo. Servono entrambi e non sono
intercambiabili: uno genera le risposte, l'altro trasforma il testo in vettori
per la ricerca semantica. Verifica che rispondano:

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

Il nome del file conta. L'ingestion ne ricava l'identificativo della macchina
(`17478_manual_EN.pdf` → `17478`) e lo salva come `machine_id` nei metadati di
ogni chunk: è la chiave con cui l'agente, a runtime, cerca solo dentro il
manuale della macchina giusta. I file con un nome che non segue lo schema
`<serialNumber>_manual_<LANG>.pdf` vengono saltati con un messaggio.

> `data/` è in `.gitignore`, quindi i PDF non finiscono mai in un commit.

## 2. Fare l'ingestion

L'agente non legge i PDF al volo: cerca in un database vettoriale (Chroma). Va
quindi popolato una volta sola, a container acceso:

```bash
docker compose exec agents python -m manuals_agent.ingestion
```

Output atteso la prima volta:

```
Ingested 15610_manual_EN.pdf (machine_id 15610): 277 chunk
Ingested 17203_manual_EN.pdf (machine_id 17203): 263 chunk
...
```

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
  -d '{"query": "What safety precautions should be taken before maintenance?", "machine_id": "17478"}'
```

`machine_id` deve essere uno degli otto identificativi ricavati dai nomi dei
file. Se la risposta contiene `citations` con `doc` e `page` reali, il RAG
funziona.

Se `citations` è vuoto e `confidence` è `0.0`: o l'ingestion non è stata fatta,
o il `machine_id` non corrisponde a nessun manuale indicizzato.

## Per lo sviluppo in locale

Per lavorare sugli agenti fuori da Docker (venv, uvicorn, test dei due agenti
uno per uno) la guida completa è in [`agents/README.md`](agents/README.md).

---

# Backend

_Da completare a cura di chi lavora sul backend: variabili d'ambiente, `.env`,
eventuali passaggi di inizializzazione._

# Frontend

_Da completare a cura di chi lavora sul frontend._

# Mock-backoffice

_Da completare._
