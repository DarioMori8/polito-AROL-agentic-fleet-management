# Agents

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
> ollama pull llama3.1:8b
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

## 4. Clonare la repo ed entra in agents

```bash
git clone <URL-del-repo>
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
```

Se hai scaricato un modello di chat diverso al punto 2, aggiorna `OLLAMA_MODEL` di conseguenza. `EMBEDDING_MODEL` e `CHROMA_PATH` puoi lasciarli come sono.

## 7. Popolare il database vettoriale (una tantum)

Il Manuals Agent risponde cercando nel manuale tramite un database vettoriale (Chroma), non leggendo il PDF al volo. Prima del primo utilizzo va quindi fatta una volta l'**ingestion**: si legge il PDF di esempio già incluso in `manuals_agent/samples_manual/`, lo si spezza in porzioni di testo (chunk), si calcola un embedding per ciascuna con `nomic-embed-text`, e si salva tutto in `data/chroma/` (cartella creata automaticamente, non tracciata da git).

```bash
python -m manuals_agent.ingestion
```

Output atteso (la prima volta):

```
Ingested A3279usomanutenzione-R1-ENG.pdf: 407 chunk
```

Lo script è idempotente: se lo rilanci e il database è già popolato, non duplica nulla:

```
Already seeded collection.
```

> Se in futuro aggiungi altri PDF, mettili nella stessa cartella `manuals_agent/samples_manual/` e rilancia lo script — verranno ingeriti solo se il database è ancora vuoto (per forzare un re-ingestion completo, cancella la cartella `data/chroma/` e rilancia).

## 8. Avviare il server

```bash
uvicorn main:app --reload --port 8001
```

Output atteso:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8001
```

Se la porta è già occupata, usa `--port 8002` (e aggiorna gli URL sotto di conseguenza).

## 9. Testare un prompt reale

1. Apri il browser su `http://localhost:8001/docs`
2. Clicca su **`POST /agents/manuals/search`** per espanderlo
3. Clicca su **"Try it out"**
4. Sostituisci il body con uno di questi esempi (`machine_id` deve essere `"generic"` — è quello usato per il seed del manuale di esempio):

   ```json
   {
     "query": "What safety precautions should be taken before maintenance?",
     "machine_id": "generic"
   }
   ```

   oppure:

   ```json
   {
     "query": "What should I check on the pneumatic system before repair?",
     "machine_id": "generic"
   }
   ```

5. Clicca **"Execute"**
6. Attendi la risposta (con `gpt-oss:20b` può richiedere da pochi secondi a circa un minuto, a seconda della GPU) — sotto apparirà "Response body" con `Code: 200`, un `answer` testuale e una lista `citations` con `doc`/`page`/`snippet` presi davvero dal PDF (non inventati)

Se la risposta contiene `citations` con pagine valide del manuale (es. `"page": 120`), il flusso end-to-end funziona correttamente.

## Troubleshooting

| Problema | Causa probabile |
|---|---|
| `ModuleNotFoundError` all'avvio di uvicorn | Venv non attivato, o `pip install -r requirements.txt` non eseguito (o eseguito prima che venissero aggiunte le dipendenze `chromadb`/`ollama`/`pymupdf` — rilancia il comando) |
| Timeout / risposta molto lenta | Modello troppo pesante per la GPU/VRAM disponibile — prova `llama3.1:8b` |
| `Connection refused` su `localhost:11434` | Ollama non è avviato — su Linux: `ollama serve` in un altro terminale |
| `ValueError: The ollama python package is not installed` | Manca la dipendenza `ollama` (diversa da `ollama` CLI) — `pip install -r requirements.txt` |
| 422 su `/agents/manuals/search` | Il body non è JSON valido — controlla di usare virgolette dritte `"` e non tipografiche `" "` |
| Risposta senza `citations` / l'agente dice di non trovare l'informazione | Non hai eseguito lo step 7 (ingestion), oppure hai usato un `machine_id` diverso da `"generic"` |
| `collection.count()` resta a 0 dopo l'ingestion | Il PDF in `manuals_agent/samples_manual/` non è leggibile/è vuoto, o `CHROMA_PATH` punta altrove rispetto a dove ti aspetti — controlla il valore in `.env` |
