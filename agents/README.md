# Agents

Questo servizio contiene **due agenti**, entrambi esposti come endpoint HTTP:

| Agente | Endpoint | A cosa risponde | Fonte dati |
|---|---|---|---|
| **Manuals Agent** | `POST /agents/manuals/search` | Domande sul manuale tecnico della macchina | PDF indicizzati in Chroma (locale) |
| **Docs Agent** | `POST /agents/docs/search` | Domande su preventivi, ordini e documenti contrattuali | servizio `mock-backoffice` via HTTP |

I due agenti hanno prerequisiti diversi: il Manuals Agent ha bisogno dei manuali e della loro ingestion (step 7 e 8), il Docs Agent ha bisogno del servizio `mock-backoffice` acceso (step 9). Se ti interessa provarne uno solo, puoi saltare lo step dell'altro.

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

Il nome del file non è decorativo: l'ingestion ne ricava l'identificativo della macchina (`17478_manual_EN.pdf` → `17478`) e lo salva come `machine_id` nei metadati di ogni chunk. Nel dataset quell'identificativo è il **serial number**, ed è la chiave che lega una macchina al suo manuale: i manuali sono specifici della singola macchina fisica, non del modello, quindi due macchine dello stesso modello hanno manuali diversi e non intercambiabili. I file il cui nome non segue lo schema `<serialNumber>_manual_<LANG>.pdf` vengono saltati con un messaggio.

> La cartella `data/` è in `.gitignore`, quindi i PDF restano sulla tua macchina e non finiscono mai in un commit.

## 8. Popolare il database vettoriale (una tantum, serve solo al Manuals Agent)

Il Manuals Agent risponde cercando nei manuali tramite un database vettoriale (Chroma), non leggendo i PDF al volo. Prima del primo utilizzo va quindi fatta una volta l'**ingestion**: si leggono i PDF da `data/manuals/`, si spezza il testo in porzioni (chunk), si calcola un embedding per ciascuna con `nomic-embed-text`, e si salva tutto in `data/chroma/` (cartella creata automaticamente, non tracciata da git).

```bash
python -m manuals_agent.ingestion
```

> **Se stai usando Docker Compose** invece del setup locale, gli step 4, 5, 6 e 10 non ti servono — il container ha già il suo ambiente, e `data/manuals/` gli è montata in sola lettura su `/data/manuals`. L'unico step che resta necessario è il 7, mettere i PDF nella cartella. Il comando di ingestion diventa:
>
> ```bash
> docker compose exec agents python -m manuals_agent.ingestion
> ```
>
> Ollama resta comunque sull'host anche in questo caso: il container lo raggiunge su `host.docker.internal:11434`.

Output atteso (la prima volta):

```
Ingested 15610_manual_EN.pdf (machine_id 15610): 277 chunk
Ingested 17203_manual_EN.pdf (machine_id 17203): 263 chunk
Ingested 17478_manual_EN.pdf (machine_id 17478): 495 chunk
Ingested 17579_manual_EN.pdf (machine_id 17579): 252 chunk
Ingested A2055_manual_EN.pdf (machine_id A2055): 201 chunk
Ingested A2064_manual_EN.pdf (machine_id A2064): 222 chunk
Ingested A2132_manual_EN.pdf (machine_id A2132): 171 chunk
Ingested A4344_manual_EN.pdf (machine_id A4344): 274 chunk
```

> **Mettici in conto parecchi minuti.** Sono 2155 chunk in totale e ognuno richiede una chiamata di embedding a Ollama: con GPU sono minuti, su CPU parecchi di più. Lascialo lavorare fino in fondo.

Lo script è idempotente **per singolo manuale**: se lo rilanci, quelli già indicizzati vengono saltati e viene ingerito solo ciò che manca.

```
Already ingested 15610_manual_EN.pdf
```

Questo vuol dire che se aggiungi un nono PDF in `data/manuals/` ti basta rilanciare lo script: verrà ingerito solo quello. E se un'esecuzione si interrompe a metà, rilanciandola riparte da dove si era fermata.

> Per forzare un re-ingestion completo, cancella la cartella `data/chroma/` e rilancia. Serve, per esempio, se cambi `EMBEDDING_MODEL`: embedding calcolati con modelli diversi non sono confrontabili tra loro.

## 9. Avviare il mock-backoffice (serve solo al Docs Agent)

Il Docs Agent non legge file locali: interroga via HTTP il servizio `mock-backoffice`, che sta al posto dell'ERP/CRM reale di AROL (preventivi, ordini, documenti contrattuali). Va avviato **in un terminale separato**, e ha un suo venv indipendente da quello di `agents`.

```bash
cd ../mock-backoffice
python3.12 -m venv .venv
```

Attiva il venv (`.venv\Scripts\Activate.ps1` su Windows, `source .venv/bin/activate` su Linux), poi:

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8003
```

Verifica in un altro terminale che risponda:

```bash
curl http://localhost:8003/health
```

Deve restituire `{"status":"ok"}`. **Lascia questo terminale aperto.**

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
4. Sostituisci il body con uno di questi esempi. `machine_id` deve essere uno degli otto identificativi dello step 7, cioè quelli ricavati dai nomi dei file (qui `17478`):

   ```json
   {
     "query": "What safety precautions should be taken before maintenance?",
     "machine_id": "17478"
   }
   ```

   oppure:

   ```json
   {
     "query": "What should I check on the pneumatic system before repair?",
     "machine_id": "17478"
   }
   ```

5. Clicca **"Execute"**
6. Attendi la risposta (con `gpt-oss:20b` può richiedere da pochi secondi a circa un minuto, a seconda della GPU) — sotto apparirà "Response body" con `Code: 200`, un `answer` testuale e una lista `citations` con `doc`/`page`/`snippet` presi davvero dal PDF (non inventati)

Se la risposta contiene `citations` con pagine valide del manuale (es. `"page": 120`), il flusso end-to-end funziona correttamente.

## 12. Testare il Docs Agent

Stessa procedura, ma su **`POST /agents/docs/search`**. Qui invece `machine_id` deve essere `"generic"`: il Docs Agent legge i dati mock del `mock-backoffice`, tutti riferiti all'unica macchina di esempio (una A3279 venduta a "BevPack S.p.A."), e non è ancora allineato ai serial number del dataset.

L'agente ha tre tool e **sceglie da solo quale usare** in base alla domanda, quindi le quattro domande qui sotto esercitano percorsi diversi. Provale in ordine:

**a) Documenti contrattuali**

```json
{
  "query": "How long is the warranty on my machine?",
  "machine_id": "generic"
}
```

Risposta attesa: 24 mesi sulle parti meccaniche, 12 sui componenti elettronici, con in `sources` il contratto `DOC-2026-001`.

**b) Ordini**

```json
{
  "query": "Which of my spare parts orders have been shipped but not delivered yet?",
  "machine_id": "generic"
}
```

Risposta attesa: solo `ORD-2026-002`.

**c) Preventivi e storico revisioni**

```json
{
  "query": "Why did the price of quote Q-2026-001 change during the negotiation?",
  "machine_id": "generic"
}
```

Risposta attesa: le 3 revisioni del preventivo (135.000 → 130.200 → 128.500 EUR) con le relative motivazioni.

**d) Domanda che incrocia due fonti** — è il test più interessante, perché costringe l'agente a chiamare **due tool diversi** e a combinarne i risultati:

```json
{
  "query": "For order ORD-2026-001, what did I buy and what are the payment terms in its contract?",
  "machine_id": "generic"
}
```

Risposta attesa: la lista degli articoli ordinati **e** i termini di pagamento (30% / 40% / 30%), con in `sources` sia un elemento `"kind": "order"` sia uno `"kind": "document"`.

### Come leggere la risposta

```json
{
  "answer": "testo della risposta",
  "sources": [ { "kind": "document | order | quote", "...": "..." } ],
  "confidence": 1.0
}
```

Il campo `kind` dice da quale fonte arriva ogni elemento, così il frontend può renderizzare un ordine come tabella e un documento come citazione. Se `sources` è vuoto e `confidence` è `0.0`, l'agente non ha trovato nulla e te lo dice onestamente invece di inventare (comportamento voluto).

## Troubleshooting

| Problema | Causa probabile |
|---|---|
| `ModuleNotFoundError` all'avvio di uvicorn | Venv non attivato, o `pip install -r requirements.txt` non eseguito (o eseguito prima che venissero aggiunte le dipendenze `chromadb`/`ollama`/`pymupdf` — rilancia il comando) |
| Timeout / risposta molto lenta | Modello troppo pesante per la GPU/VRAM disponibile — prova `llama3.1:8b` |
| `Connection refused` su `localhost:11434` | Ollama non è avviato — su Linux: `ollama serve` in un altro terminale |
| `ValueError: The ollama python package is not installed` | Manca la dipendenza `ollama` (diversa da `ollama` CLI) — `pip install -r requirements.txt` |
| 422 su uno dei due endpoint | Il body non è JSON valido — controlla di usare virgolette dritte `"` e non tipografiche `" "` |
| **Manuals**: risposta senza `citations` / l'agente dice di non trovare l'informazione | Non hai eseguito lo step 8 (ingestion), oppure il `machine_id` passato non è uno degli 8 ricavati dai nomi dei manuali |
| **Manuals**: `No pdf found in ...` all'ingestion | I PDF non sono in `data/manuals/` (step 7), o `MANUALS_PATH` nel `.env` punta altrove — da dentro `agents/` deve valere `../data/manuals` |
| **Manuals**: `Skipped <file>: expected <serialNumber>_manual_<LANG>.pdf` | Il file non rispetta la convenzione di nome del dataset: rinominalo, non cambiare lo script |
| **Manuals**: citazioni prese dal manuale di un'altra macchina | Non dovrebbe succedere: la ricerca è filtrata per `machine_id`. Se capita, i chunk in Chroma sono stati indicizzati con una versione precedente dell'ingestion, quando tutti i chunk erano marcati `"generic"` — cancella `data/chroma/` e rifai lo step 8 |
| **Docs**: `httpx.ConnectError` / `Connection refused` su `localhost:8003` | Il `mock-backoffice` non è avviato — vedi step 9, va tenuto acceso in un terminale separato |
| **Docs**: `sources` sempre vuoto e `confidence: 0.0` | `machine_id` diverso da `"generic"` (i dati mock esistono solo per quella macchina), oppure `DOCS_SERVICE_URL` nel `.env` punta a una porta sbagliata |
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
