# AROL Customer Platform — Backend & Orchestrator

Backend service that exposes the chat API consumed by the frontend, and
orchestrates calls to the specialized AI Agents (starting with the
Manuals Agent) through an LLM-based orchestrator.

This is **iteration 2**: the orchestrator now decides which agent(s) to
call via LLM tool-calling (function calling), instead of the hardcoded
routing of iteration 1. With a single agent (Manuals) registered, the
practical effect is similar, but the routing decision is now made by an
LLM reading tool descriptions — not by a fixed call in the endpoint.
This is the foundation for adding more agents (IoT, Orders,
Troubleshooting, ...) without touching the API layer.

```
Frontend (simulated via Swagger UI)
    → Backend API (/v1/chat)
    → Orchestrator (LLMOrchestrator)
        → Orchestrator's own LLM (Ollama, tool-calling loop)
        → Agent Registry (tool name → handler)
            → ManualsClient → Manuals Agent (Ollama-based)
```

## Project structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app entrypoint, mounts routers, configures logging
│   ├── config.py                  # Settings loaded from .env (Pydantic Settings)
│   ├── api/
│   │   └── v1/
│   │       └── chat.py            # POST /v1/chat — delegates entirely to the orchestrator
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── base.py                # Orchestrator ABC (interface/implementation decoupling)
│   │   ├── llm_adapter.py          # LLM adapter used for routing/tool-calling/composition
│   │   ├── agent_registry.py       # Maps each tool the LLM can call to its handler function
│   │   └── orchestrator.py         # LLMOrchestrator: the reason -> act -> observe loop
│   ├── clients/
│   │   ├── base.py                # Abstract interface for agent clients
│   │   ├── manuals_client.py      # HTTP client for the Manuals Agent
│   │   └── exceptions.py          # AgentUnavailableError (domain-level error)
│   └── models/
│       └── chat.py                # ChatRequest / ChatResponse (endpoint contract)
├── requirements.txt
├── .env.example
├── .dockerignore
└── Dockerfile
```

## What each part does

### `app/main.py`
Creates the single FastAPI application instance, includes all routers,
and configures logging (`logging.basicConfig`) — required for the
`logger.info(...)` calls in the orchestrator to actually appear in the
console; without it, Python's default handler suppresses anything
below `WARNING`.

### `app/config.py`
Centralizes all configuration using `pydantic-settings`. Now includes
two separate sets of LLM settings: one for the Manuals Agent's own
model (unchanged) and one for the orchestrator's routing model
(`ORCHESTRATOR_*`). These are intentionally independent — the
orchestrator's LLM does not have to be the same model/provider as any
agent's, since its job (routing + composing) is lighter than an
agent's own reasoning over its domain data.

### `app/api/v1/chat.py`
The HTTP-facing layer. Validates the incoming `ChatRequest`, delegates
entirely to `LLMOrchestrator.handle(...)`, and returns its
`ChatResponse`. Contains no business logic and no networking code —
does not know which agents exist.

### `app/orchestrator/`
- **`base.py`** — abstract `Orchestrator` interface (`handle(request) -> ChatResponse`).
  Kept as an ABC to decouple the API layer from the concrete
  implementation, even though `LLMOrchestrator` is currently the only
  one; documented as a deliberate architectural choice rather than a
  requirement of the current implementation.
- **`llm_adapter.py`** — adapter to the orchestrator's own LLM (Ollama).
  Structurally mirrors `agents/core/llm_adapter.py` (same `ToolCall` /
  `LLMResponse` shapes); flagged as temporary duplication, see "Known
  limitations".
- **`agent_registry.py`** — the single place that lists available
  agents as LLM tool definitions (name, description, JSON-schema
  parameters) and pairs each with a *handler*: an `async (dict) -> dict`
  function that translates the LLM's generic arguments into the
  specific, typed call on the concrete agent client (e.g.
  `ManualsClient.search(query, machine_id)`), and normalizes the
  client's typed response back into a plain dict. Adding a new agent
  later means adding one entry here — nothing else changes.
- **`orchestrator.py`** — `LLMOrchestrator`, implementing the
  reason -> act -> observe loop: calls the LLM with the available
  tools, executes any requested tool call via the registry, feeds the
  result back, and repeats (bounded by `ORCHESTRATOR_MAX_ITERATIONS`)
  until the LLM responds with plain text instead of a tool call. Logs
  every step (`logger.info`) for observability during development.

### `app/clients/`
One client class per agent, each implementing a shared abstract
interface (`base.py`). A client's only job is to know how to talk to
one specific agent over HTTP — building the request, handling
timeouts/retries, and translating low-level `httpx` errors into a
single domain-level `AgentUnavailableError`. This isolates the
orchestrator from networking details entirely: if the transport layer
changes later (e.g. moving to MCP), only the client implementation
needs to change.

`manuals_client.py` also applies automatic retry (via `tenacity`) on
transient network errors (timeout, connection refused), but not on
HTTP error status codes, since those usually indicate a logic error
rather than a temporary glitch.

### `app/models/`
Pydantic schemas shared with the Agents project via the `contracts`
package (e.g. `SearchManualResponse`, `Citation`). `app/models/chat.py`
defines `ChatRequest`/`ChatResponse`, the contract for the `/v1/chat`
endpoint itself (not shared with the agents project, since it's
backend/frontend-specific).

## Requirements

- Python 3.12
- Ollama running locally, with **two** models pulled:
  - one for the Manuals Agent (see `agents/README.md`)
  - one for the orchestrator's routing/tool-calling (see below) — must
    support tool calling; `llama3.1:8b` and `gpt-oss:20b` both do
- The Manuals Agent running and reachable

## Local setup

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate        # Linux
# .\venv\Scripts\Activate.ps1   # Windows PowerShell

pip install -r requirements.txt

cp .env.example .env
# edit .env if needed, in particular MANUALS_AGENT_URL and ORCHESTRATOR_OLLAMA_MODEL
```

## Running locally

You need **two services running in parallel** (plus `ollama serve`
running separately), in two separate terminals:

**Terminal 1 — Manuals Agent** (see `agents/README.md` for full setup):
```bash
cd agents
uvicorn main:app --reload --port 8001
```

**Terminal 2 — Backend**:
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Then open `http://localhost:8000/docs` and try `POST /v1/chat` with:
```json
{
  "query": "perché la macchina non funziona?",
  "machine_id": "2"
}
```

Watch Terminal 2's console: the orchestrator logs each step (LLM call,
tool(s) requested, tool result, next iteration) so you can follow the
routing decision in real time.

## Environment variables (`.env`)

| Variable                       | Description                                          | Example                  |
|---------------------------------|-------------------------------------------------------|---------------------------|
| `MANUALS_AGENT_URL`             | Base URL of the Manuals Agent service                 | `http://localhost:8001`  |
| `ORCHESTRATOR_LLM_PROVIDER`     | LLM provider used by the orchestrator                  | `ollama`                  |
| `ORCHESTRATOR_OLLAMA_BASE_URL`  | Base URL of the Ollama server for the orchestrator     | `http://localhost:11434` |
| `ORCHESTRATOR_OLLAMA_MODEL`     | Model used for routing/tool-calling (must support it)  | `llama3.1:8b`             |
| `ORCHESTRATOR_MAX_ITERATIONS`   | Max reason/act/observe iterations before giving up      | `5`                       |

## Known limitations / next steps


- **No persistence yet** — no database, no session/conversation memory.
  `ChatRequest` has no `conversation_history` field yet. Planned for a
  later iteration (Postgres for structured data, Redis for
  session/cache).
- **No authentication** on the `/v1/chat` endpoint yet.
- **No automated evaluation of routing quality** — nothing currently
  measures whether the LLM's decision to stop (or keep calling tools)
  was actually correct; relies entirely on the system prompt and the
  model's own judgment. A `confidence`-based check or a separate judge
  step are possible future additions.
