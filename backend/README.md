# AROL Customer Platform — Backend & Orchestrator

Backend service that exposes the chat API consumed by the frontend, and
orchestrates calls to the specialized AI Agents (starting with the
Manuals Agent) through an LLM-based orchestrator built on **LangGraph**.

This is **iteration 3**: the orchestrator's reason -> act -> observe
loop, previously implemented as a hand-written `for` loop (iteration 2),
is now expressed as a compiled **LangGraph** `StateGraph`. The routing
decision itself is unchanged (an LLM reading tool descriptions decides
which agent(s) to call) — what changes is the engine that drives the
loop, in exchange for built-in tool execution (`ToolNode`), a
ready-made conditional-routing helper (`tools_condition`), and a
foundation for checkpointing (session persistence, not yet wired) and
tracing (Langfuse, not yet wired). 
```
Frontend (simulated via Swagger UI)
    → Backend API (/v1/chat)
    → Orchestrator (LangGraphOrchestrator)
        → StateGraph: agent node (ChatOllama + bound tools)
            --(tool_calls?)--> tools node (ToolNode)
                → ManualsClient → Manuals Agent (Ollama-based)
            <-- loops back to agent node until plain-text response
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
│   │   ├── agent_registry.py       # LangChain @tool-decorated functions, one per agent
│   │   └── orchestrator.py         # LangGraphOrchestrator: StateGraph-based reason/act/observe loop
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
and configures logging.

### `app/config.py`
Centralizes all configuration using `pydantic-settings`. Two
independent sets of LLM settings: one for the Manuals Agent's own model
(unchanged) and one for the orchestrator's routing model
(`ORCHESTRATOR_*`), including `ORCHESTRATOR_NUM_CTX` — the context
window is now fixed explicitly rather than left to `ChatOllama`'s
default, since a mismatch here can silently push VRAM usage past what's
available and force CPU offload (5-30x slowdown). Verify actual GPU
placement any time with `ollama ps` (`PROCESSOR` column should read
`100% GPU`).

### `app/api/v1/chat.py`
The HTTP-facing layer. Validates the incoming `ChatRequest`, delegates
entirely to `LangGraphOrchestrator.handle(...)`, and returns its
`ChatResponse`. Contains no business logic and no networking code —
does not know which agents exist.

### `app/orchestrator/`
- **`base.py`** — abstract `Orchestrator` interface (`handle(request) -> ChatResponse`).
  Kept as an ABC to decouple the API layer from the concrete
  implementation; documented as a deliberate architectural choice
  rather than a requirement of the current implementation.
- **`agent_registry.py`** — one `@tool`-decorated async function per
  agent (currently `search_manuals`). LangChain inspects the function's
  typed signature and docstring to generate the tool schema
  automatically — no manual JSON schema or dict-argument translator
  needed anymore (unlike iteration 2's `AgentTool`/`ToolHandler`). Each
  tool uses `@tool(response_format="content_and_artifact")`, returning
  a `(content, artifact)` tuple: `content` (string) is what the LLM
  reads to reason/compose; `artifact` (a real dict) is what
  `orchestrator.py` reads back to extract structured citations —
  **this parameter is required**, a plain `@tool` silently breaks
  citation extraction with no error. Adding a new agent means adding one `@tool`
  function here — nothing else changes.
- **`orchestrator.py`** — `LangGraphOrchestrator`, wrapping a compiled
  `StateGraph`: an `agent` node (calls `ChatOllama`, bound to
  `AGENT_TOOLS` once at module load, not per call) and a `tools` node
  (`ToolNode`, executes whatever the LLM requested), connected by a
  conditional edge (`tools_condition`) that loops back to `agent` until
  the LLM responds with plain text. `recursion_limit` (passed to
  `graph.ainvoke`) counts every node execution, not full reason/act
  cycles — computed as `ORCHESTRATOR_MAX_ITERATIONS * 2 + 1`, an
  approximation to re-tune with real testing.

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
- `langgraph`, `langchain-ollama` (see `requirements.txt`)
- Ollama running locally, with model(s) pulled that support tool
  calling `gpt-oss:20b`. Currently the same
  model is used for both the orchestrator and the Manuals Agent — see
  "Known limitations" regarding the VRAM/latency trade-offs of this
  choice.
- The Manuals Agent running and reachable

## Local setup

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate        # Linux
# .\venv\Scripts\Activate.ps1   # Windows PowerShell

pip install -r requirements.txt

cp .env.example .env
# edit .env if needed, in particular MANUALS_AGENT_URL, ORCHESTRATOR_OLLAMA_MODEL, ORCHESTRATOR_NUM_CTX
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

Test with curl:
```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "perché la macchina non parte", "machine_id": "2"}'
```

or via `http://localhost:8000/docs`.

To check GPU/VRAM placement while testing (useful for diagnosing
slowdowns), run in a third terminal:
```bash
ollama ps
```
`PROCESSOR` should read `100% GPU`; anything showing a CPU split means
the model has spilled out of VRAM.

**Note on visibility**: the manual `logger.info(...)` step-by-step
logging from iteration 2 was intentionally not carried over to the
LangGraph version — Langfuse (not yet integrated, see "Known
limitations") is meant to replace it properly. In the meantime, a
temporary debug print of `result["messages"]` inside `handle()` is the
quickest way to inspect a run's full message history.

## Environment variables (`.env`)

| Variable                       | Description                                            | Example                  |
|---------------------------------|-----------------------------------------------------------|---------------------------|
| `MANUALS_AGENT_URL`             | Base URL of the Manuals Agent service                     | `http://localhost:8001`  |
| `ORCHESTRATOR_LLM_PROVIDER`     | LLM provider used by the orchestrator                     | `ollama`                  |
| `ORCHESTRATOR_OLLAMA_BASE_URL`  | Base URL of the Ollama server for the orchestrator        | `http://localhost:11434` |
| `ORCHESTRATOR_OLLAMA_MODEL`     | Model used for routing/tool-calling (must support it)     | `gpt-oss:20b`             |
| `ORCHESTRATOR_NUM_CTX`          | Context window fixed explicitly (see `config.py` notes)   | `4096`                    |
| `ORCHESTRATOR_MAX_ITERATIONS`   | Max reason/act/observe cycles before giving up             | `5`                       |

## Known limitations / next steps

- **Langfuse not yet integrated** — no persistent, queryable trace of
  requests; only the temporary manual `print` debugging described
  above. This is the next planned step (see
  `MIGRAZIONE_LANGGRAPH_TEORIA.md`, section 5).
- **No checkpointing yet** — `StateGraph` supports persistence
  (`SqliteSaver`/`PostgresSaver`) but it isn't wired in. `ChatRequest`
  still has no `conversation_history` field. Planned as part of the
  LangGraph migration's remaining work.
- **Same model used for both the orchestrator and the Manuals Agent**
  (`gpt-oss:20b`) — chosen for simplicity/VRAM-safety on 16GB hardware
  (no model-swapping), at the cost of using a heavier-than-necessary
  model for the lightweight routing task. Not yet benchmarked against a
  smaller dedicated orchestrator model on equal footing (same test,
  same model choice as the pre-migration baseline) to isolate whether
  perceived slowdowns come from the model choice or the framework
  itself.
- **No automated evaluation of routing quality** — nothing currently
  measures whether the LLM's decision to stop (or keep calling tools)
  was actually correct; relies entirely on the system prompt and the
  model's own judgment. A `confidence`-based check or a separate judge
  step are possible future additions.
- **No authentication** on the `/v1/chat` endpoint yet.
- **Single agent registered** (`search_manuals`). Real multi-agent
  routing (IoT, Orders, Troubleshooting) is the next milestone — each
  new agent needs one client in `app/clients/` and one `@tool` function
  in `agent_registry.py`, nothing else.