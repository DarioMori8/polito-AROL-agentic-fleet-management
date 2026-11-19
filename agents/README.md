# Agents

FastAPI service with the three specialized agents called by the backend orchestrator.

| Agent | Endpoint | Answers about | Data source |
|---|---|---|---|
| Manuals | `POST /agents/manuals/search` | The technical manual of one machine | PDFs indexed in Chroma |
| Docs | `POST /agents/docs/search` | Quotes and orders of a company | `mock-backoffice` over HTTP |
| IoT | `POST /agents/iot/search` | Telemetry, alarms and maintenance tickets of one machine | `mock-backoffice` over HTTP |

Each agent runs the same loop (`core/base_agent.py`): the LLM picks a tool, the code runs it, the result goes back to the LLM, until it answers without tool calls. `MAX_ITERATIONS` is only a safety limit. The scope fields of the request (`machine_id`, `company_id`) are never exposed in the tool schemas, so the LLM cannot widen the search.

## Structure

```
agents/
├── main.py              # FastAPI app and the three endpoints
├── core/
│   ├── config.py        # Settings (reads the root .env)
│   ├── base_agent.py    # shared tool-calling loop
│   ├── llm_adapter.py   # Ollama client
│   ├── vectorstore.py   # Chroma client
│   ├── docs_client.py   # mock-backoffice client for commercial data
│   ├── iot_client.py    # mock-backoffice client for operational data
│   └── observability.py # Langfuse setup
├── manuals_agent/       # agent, tools, prompts, ingestion
├── docs_agent/          # agent, tools, prompts
├── iot_agent/           # agent, tools, prompts
├── tests/
└── data/chroma/         # Chroma index, created by the ingestion (not versioned)
```

Request and response schemas are in `shared/contracts/` (`manuals.py`, `docs.py`, `iot.py`), shared with the backend.

## The agents

### Manuals

- Tool: `search_manual`, a semantic search in Chroma filtered by `machine_id`.
- Manuals are in English: the agent searches in English and answers in the language of the question.
- Response: `answer`, `citations` (`doc`, `page`, `snippet`), `confidence`. An empty answer returns `confidence: 0.0`.

### Docs

- Tools: `search_orders` and `search_quotes`.
- Request: `query`, `company_id` (required), `machine_id` (optional).
- Commercial data belongs to the company, not to the machine. An order reaches a machine only through the lines of a quote revision, and a quote for a machine not yet installed has no machine at all. That's why `company_id` is the scope and `machine_id` only narrows it.
- Response: `answer`, `sources` (with `kind`: `order` or `quote`), `confidence`.

### IoT

| Tool | Used for |
|---|---|
| `analyze_machine_health` | Overall state, last snapshot and KPIs over a time window |
| `search_telemetry` | Hourly readings in a period or in a given operational state |
| `search_alarms` | Alarms by date, severity, status or code |
| `search_maintenance` | Maintenance tickets by date, status, priority or linked alarm |
| `analyze_alarm_ticket_coverage` | Which alarms have a ticket and which don't (joined in code, not by the LLM) |

- General questions get a compact SQL summary, and detailed rows are loaded only when needed. This keeps up to 720 hourly rows per month out of the LLM context.
- The dataset ends on **4 August 2026**: "last 24 hours" means the 24 hours before the machine's last snapshot, not before the server clock.
- Response: `answer`, `observations` (with `kind`: `health`, `telemetry`, `alarms`, `maintenance`), `confidence`.

## Manual ingestion

For the self-contained delivery, ingestion runs automatically before the agents
start; see [SETUP.md](../SETUP.md). The instructions below are for the
development stack.

The Manuals Agent needs a Chroma index built from the PDFs in `data/manuals/` (repo root). The ingestion:

1. reads each `<serialNumber>_manual_<LANG>.pdf`;
2. asks the mock-backoffice which `machine_id` has that serial (`17478` → `MCH-0004`), so the mock-backoffice must be running;
3. splits the text into chunks, computes the embeddings with `nomic-embed-text` and stores them in `agents/data/chroma/`.

With Docker:

```bash
docker compose stop frontend backend agents
docker compose run --rm --no-deps agents python -m manuals_agent.ingestion
```

Then start the application again so the agents open the updated index:

```bash
docker compose up -d agents backend frontend
```

It takes several minutes (embeddings are computed in batches of 20 chunks).
Completed PDFs are tracked with a content hash and chunk count in
`ingestion-manifest.json`. Unchanged files are skipped; changed or interrupted
files are rebuilt, and removed PDFs are removed from the index. Changing
`EMBEDDING_MODEL` rebuilds the index automatically. Existing indexes without a
manifest are rebuilt once. Run ingestion while the agents are stopped to avoid
concurrent access to Chroma, then start the agents again.

## Running locally

The mock-backoffice must be running on port `8003` (see [mock-backoffice/README.md](../mock-backoffice/README.md)). The variables are read from the root `.env`.

```bash
cd agents
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m manuals_agent.ingestion
uvicorn main:app --reload --port 8001
```

## Tests

```bash
docker compose exec agents python -m unittest discover -s tests
```

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Docker: `http://host.docker.internal:11434` |
| `OLLAMA_MODEL` | — (required) | `gpt-oss:20b` |
| `OLLAMA_NUM_CTX` | `16384` | Context window for multi-step retrieval |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Changing it requires a new ingestion |
| `MAX_ITERATIONS` | `5` | Max tool rounds per request |
| `CHROMA_PATH` | `./data/chroma` | |
| `MANUALS_PATH` | `/data/manuals` | Locally `../data/manuals` |
| `DOCS_SERVICE_URL`, `IOT_SERVICE_URL` | `http://localhost:8003` | Docker: `http://mock-backoffice:8003` |
| `LANGFUSE_*` | — | Without keys the agents run without tracing |

## Tracing

The agents send their traces to the same Langfuse project as the backend. The backend propagates the trace context in the `traceparent` and `baggage` headers, so in Langfuse each chat turn shows `orchestrator → search_* → *.http → agent → iterations / tools / LLM` in one trace. The tracing headers carry observability only, never authorization.

## Trying the endpoints

Interactive docs: `http://localhost:8001/docs`. The machines are `MCH-0001` … `MCH-0008`; `curl http://localhost:8003/machines` shows their companies.

```bash
curl -X POST http://localhost:8001/agents/manuals/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What safety precautions should be taken before maintenance?", "machine_id": "MCH-0004"}'
```

```bash
curl -X POST http://localhost:8001/agents/docs/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Why did the price of quote QTE-2025-0001 change?", "company_id": "CMP-001", "machine_id": "MCH-0001"}'
```

```bash
curl -X POST http://localhost:8001/agents/iot/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Which open alarms already have a ticket?", "machine_id": "MCH-0007"}'
```

## Troubleshooting

| Problem | Likely cause |
|---|---|
| Manuals: no `citations`, `confidence: 0.0` | Ingestion not done, or `machine_id` not in `MCH-0001`…`MCH-0008` |
| Ingestion: `No pdf found in ...` | PDFs not in `data/manuals/`, or wrong `MANUALS_PATH` |
| Ingestion: `Skipped <file>: expected <serialNumber>_manual_<LANG>.pdf` | Rename the file to the dataset convention |
| Ingestion: `serial ... is not in the fleet registry` | Wrong workbook in `mock-backoffice/dataset/` |
| `chromadb … Error finding id` | Ingestion ran while the server was up: restart the agents |
| `httpx.ConnectError` on port 8003 | mock-backoffice not running |
| Docs: empty `sources` | `company_id` does not own that machine |
| `Connection refused` on port 11434 | Ollama not running (on Linux also check `OLLAMA_HOST`, see the root README) |
| Very slow answers | Model too large for the GPU: check `ollama ps` |

## Known limitations

- Manuals are read from a shared folder. The planned design is upload through the backend, which then sends each new PDF to an ingestion endpoint of the agents.
- Only Ollama is supported as LLM provider (`LLM_PROVIDER=ollama`).
