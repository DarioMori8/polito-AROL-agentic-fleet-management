# AROL Customer Platform — Backend & Orchestrator

Backend service that exposes the chat API consumed by the frontend, and
orchestrates calls to the specialized AI Agents (starting with the
Manuals Agent).

This is **iteration 1**: a single agent (Manuals) wired end-to-end
through the backend, with hardcoded routing (no real intent-routing
logic yet). The goal of this iteration was to validate the full chain:

```
Frontend (simulated via Swagger UI) → Backend API → Orchestrator → ManualsClient → Manuals Agent (Ollama-based)
```

## Project structure

```
backend/
├── app/
│   ├── main.py                # FastAPI app entrypoint, mounts routers
│   ├── config.py              # Settings loaded from .env (Pydantic Settings)
│   ├── api/
│   │   └── v1/
│   │       └── chat.py        # POST /v1/chat — endpoint exposed to the frontend
│   ├── orchestrator/          # Decision logic: which agent(s) to call (WIP)
│   ├── clients/
│   │   ├── base.py            # Abstract interface for agent clients
│   │   ├── manuals_client.py  # HTTP client for the Manuals Agent
│   │   └── exceptions.py      # AgentUnavailableError (domain-level error)
│   └── models/
│       └── manuals.py         # Shared Pydantic schemas (mirrors agent's schemas.py)
├── requirements.txt
├── .env.example
├── .dockerignore
└── Dockerfile
```

## What each part does

### `app/main.py`
Creates the single FastAPI application instance and includes all
routers (currently just `chat`). This is the only file that
instantiates `FastAPI()` — every other module defines an `APIRouter`
and gets mounted here.

### `app/config.py`
Centralizes all configuration (URLs, secrets, parameters) using
`pydantic-settings`. Values are read from a `.env` file. Never
hardcode URLs or credentials elsewhere in the code — always go through
`settings`.

### `app/api/v1/chat.py`
The HTTP-facing layer. Receives requests from the frontend, validates
input/output with Pydantic models, and delegates the actual work to
the orchestrator. Contains no business logic and no networking code.


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
Pydantic schemas shared with the Agents project (currently copied
manually from the agent's `schemas.py` — see "Known limitations"
below). Used to validate both outgoing requests and incoming
responses from agents.

## Requirements

- Python 3.12
- The Manuals Agent running and reachable (see `agents/README.md` for
  its setup, which requires Ollama)

## Local setup

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate        # Linux
# .\venv\Scripts\Activate.ps1   # Windows PowerShell

pip install -r requirements.txt

cp .env.example .env
# edit .env if needed, in particular MANUALS_AGENT_URL
```

## Running locally

You need **two services running in parallel**, in two separate
terminals:

**Terminal 1 — Manuals Agent** (see `agents/README.md` for full setup,
requires `ollama serve` running separately):
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

## Environment variables (`.env`)

| Variable            | Description                              | Example                  |
|---------------------|-------------------------------------------|---------------------------|
| `MANUALS_AGENT_URL`  | Base URL of the Manuals Agent service     | `http://localhost:8001`  |


## Known limitations / next steps

- **Shared schemas are duplicated manually** between `backend/app/models/`
  and the Agents project's `core/schemas.py`. If the agent changes its
  response format, this file must be updated manually. Plan: move to a
  shared installable package (`shared/contracts/`) once both projects
  stabilize.
- **Orchestrator routing is hardcoded** to always call the Manuals
  Agent — this is expected for iteration 1 (single agent). Real
  intent-routing (LLM tool calling to pick among multiple agents) is
  the next milestone once a second agent is added.
- **No persistence yet** — no database, no session/conversation memory.
  Planned for a later iteration (Postgres for structured data, Redis
  for session/cache).
- **No authentication** on the `/v1/chat` endpoint yet.