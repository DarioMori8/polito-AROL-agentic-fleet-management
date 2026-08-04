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
foundation for checkpointing. On top of this iteration, three
capabilities are now wired in: **Langfuse tracing** (via a module-level
`CallbackHandler` passed to the graph), **token-by-token streaming** of
the answer over Server-Sent Events (see the API section), and **durable
checkpointing** — the graph is compiled with an `AsyncSqliteSaver` so
that turns sharing a `session_id` accumulate into one conversation, and
that conversation survives a process restart because the state is written
to a SQLite file on disk rather than kept in RAM.
```
Frontend (simulated via Swagger UI / curl -N)
    → Backend API (/v1/chat  or  /v1/chat/stream)
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
│   │       └── chat.py            # POST /v1/chat and POST /v1/chat/stream — delegate to the orchestrator
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── base.py                # Orchestrator ABC (interface/implementation decoupling)
│   │   ├── agent_registry.py       # LangChain @tool-decorated functions, one per agent
│   │   └── orchestrator.py         # LangGraphOrchestrator: StateGraph-based reason/act/observe loop
│   ├── clients/
│   │   ├── base.py                # Abstract interface for agent clients
│   │   ├── manuals_client.py      # HTTP client for the Manuals Agent
│   │   └── exceptions.py          # AgentUnavailableError (domain-level error)
│   |── models/
│   |    └── chat.py                # ChatRequest / ChatResponse (endpoint contract)
|   └── resources/
|           |── repository.py
|           |── router.py           #GET /v1/machines/{machine_id}, GET /v1/machines/{machine_id}/manuals, GET /v1/manauls/{manual_id} and GET /v1/machines
|           └── schemas.py
|
├── requirements.txt
├── .env
├── .dockerignore
└── Dockerfile
```

## What each part does

### `app/main.py`
Creates the single FastAPI application instance, includes all routers,
and configures logging. Defines the **`lifespan`**: at startup it opens
the durable checkpointer and compiles the graph (through
`build_graph()`), wraps it in a `LangGraphOrchestrator`, and places that
on `app.state`; at shutdown the checkpointer's SQLite connection is
closed cleanly as the `async with` unwinds. This is why the graph is an
application resource created at startup, not a module-level global.

### `app/config.py`
Centralizes all configuration using `pydantic-settings`. Two
independent sets of LLM settings: one for the Manuals Agent's own model
(unchanged) and one for the orchestrator's routing model
(`ORCHESTRATOR_*`), including `ORCHESTRATOR_NUM_CTX` — the context
window is now fixed explicitly rather than left to `ChatOllama`'s
default, since a mismatch here can silently push VRAM usage past what's
available and force CPU offload (5-30x slowdown). Verify actual GPU
placement any time with `ollama ps` (`PROCESSOR` column should read
`100% GPU`). Also bridges the Langfuse credentials into `os.environ`
after building `settings`, because Langfuse's `CallbackHandler` reads
them directly from the process environment, not from the pydantic
`settings` object.

### `app/api/v1/chat.py`
The HTTP-facing layer. Validates the incoming `ChatRequest` and
delegates entirely to the orchestrator — `handle(...)` for the
non-streaming endpoint, `handle_stream(...)` for the streaming one. It
serializes the orchestrator's semantic events into the SSE wire format
(`event:`/`data:` frames), but contains no business logic and no
networking code towards the agents, and does not know which agents
exist.

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
  the LLM responds with plain text. Exposes two entry points:
  `handle()` runs the graph to completion with `graph.ainvoke(...)` and
  returns a single `ChatResponse`; `handle_stream()` runs the same
  graph with `graph.astream(stream_mode=["messages", "updates"])` and
  yields a sequence of semantic events (start / thinking / status /
  token / error / citations / done) as execution proceeds.
  `recursion_limit` (passed to the graph) counts every node execution,
  not full reason/act cycles — computed as
  `ORCHESTRATOR_MAX_ITERATIONS * 2 + 1`, an approximation to re-tune
  with real testing.
  The graph is compiled with a durable checkpointer (`AsyncSqliteSaver`),
  so each invocation is keyed by a `thread_id` passed in
  `config["configurable"]`. Both entry points derive it as
  `request.session_id or str(uuid4())` — a missing id means "new
  conversation" (generate one), a present id means "resume that thread".
  Because the saver holds an open connection to a file, the graph is no
  longer compiled at module load: it is built inside a FastAPI `lifespan`
  (via `build_graph()`, an async context manager that opens the saver and
  yields the compiled graph), and the resulting orchestrator is stored on
  `app.state`, from which the endpoints read it. The persisted state holds
  conversation messages only: the system prompt is prepended inside the
  `agent` node at call time rather than seeded into state, so it never
  accumulates across turns as `add_messages` merges each new turn onto the
  loaded history.

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
defines `ChatRequest`/`ChatResponse`, the contract for the chat
endpoints (not shared with the agents project, since it's
backend/frontend-specific). `ChatRequest.session_id` is optional —
absent on the first turn, echoed back by the client on subsequent turns
to continue the same conversation.

## API

The backend exposes three endpoints: a health check, a non-streaming
chat endpoint, and a streaming chat endpoint. The two chat endpoints
accept the **same** request body and delegate entirely to the
orchestrator; they differ only in how the answer is delivered — one JSON
block versus token-by-token. In both cases a single HTTP request carries
the user's question in and brings the assistant's answer back out; there
is no separate endpoint to "fetch" the reply afterwards.

### `GET /`

Health check. Takes no input.

**Returns**: `{"status": "ok"}`. Used to confirm the service is up.

### `POST /v1/chat`

Non-streaming chat. Receives the user's question, runs the full
orchestrator graph to completion (`graph.ainvoke`), and returns the
assembled answer as a single JSON object. This is the endpoint to use
from Swagger UI, automated tests, or any client that does not consume
SSE.
**Receives** — `ChatRequest`:

| Field        | Type  | Description |
|--------------|-------|-------------|
| `query`      | `str` | The user's question in natural language. |
| `machine_id` | `str` | Identifier of the machine the question refers to. Injected into the tool call, not treated as part of the question to interpret. |
| `session_id` | `str \| None` | Conversation id. Omit (or `null`) to start a new conversation; pass the id returned by a previous turn to continue it. |

```json
{ "query": "perché la macchina non parte", "machine_id": "2" }
```

**Returns** — `ChatResponse`:

| Field        | Type              | Description |
|--------------|-------------------|-------------|
| `answer`     | `str`             | Final assistant response, composed by the orchestrator strictly from the tool results. |
| `citations`  | `list[Citation]`  | Structured references extracted from the tool artifacts; each `Citation` has `doc`, `page`, `snippet`. Empty list if none. |
| `session_id` | `str`             | Conversation identifier (the graph's `thread_id`). Always returned — freshly generated on a new conversation, or echoed back when resuming. Send it in the next `ChatRequest` to continue the conversation. |

```json
{
  "answer": "...",
  "citations": [{ "doc": "manual_1.pdf", "page": 12, "snippet": "..." }],
  "session_id": "3f2c1a9e-8b7d-4e6f-a1c2-9d8e7f6a5b4c"
}
```

### `GET /v1/machines`

Fleet list. Takes no input. Returns every machine in the customer's
park.

**Returns**: a JSON array of machine objects, each with `id`, `name`,
`model`, `serial_number`, 
`status` (`online` / `offline` / `maintenance`) and `location` . An empty array is a
valid response (no machines catalogued).

### `GET /v1/machines/{machine_id}`

Machine detail — the landing target of the QR-scan use case. Receives a
machine id in the path and returns that single machine's record.

**Returns**: one machine object (same fields as above). Responds `404`
if no machine with that id exists. The id space is shared with the chat
endpoint's `machine_id`, so the same identifier addresses a machine
everywhere in the system.


### `GET /v1/machines/{machine_id}/manuals`
Takes no input. Returns all manuals of that machine.

**Returns**: a JSON array of manual objects, each with `id`, `machine_id`,
`title`, `filename`, `language`, `page_count`
and `url`. An empty array is a
valid response (no machines catalogued).

### `GET /v1/manuals/{manual_id}`

Manual detail, receives a
manual id in the path and returns that single manual's record.

**Returns**: one manual object (same fields as above). Responds `404`
if no manual with that id exists. 



### `POST /v1/chat/stream`

Streaming chat over **Server-Sent Events (SSE)**. Receives the same
`ChatRequest`, but instead of returning one JSON object it keeps the HTTP
response open and streams a sequence of typed events as the graph
executes (`graph.astream`), so the frontend can render the answer as it
forms. The question travels in the request body; the whole answer
streams back on the same connection.

**Receives**: identical to `POST /v1/chat` (`query`, `machine_id`).

**Returns**: `Content-Type: text/event-stream`. Each event is one SSE
frame of the form `event: <type>\ndata: <json>\n\n`, where the `data`
payload is a JSON object whose `type` field matches the event name.

Event sequence for a typical turn:

| Event       | When | `data` payload |
|-------------|------|----------------|
| `start`     | Once, before the graph runs | `{ "type": "start", "session_id": "<uuid>" }` — the conversation id (echoed from the request if resuming, freshly generated otherwise), sent first so the frontend has it from the first byte. |
| `thinking`  | While the routing LLM reasons (model-dependent) | `{ "type": "thinking", "text": "<chunk>" }` — reasoning tokens, delivered on a channel separate from the answer, meant to be shown collapsed/greyed. |
| `status`    | When the LLM decides to call an agent | `{ "type": "status", "tool": "search_manuals", "message": "Consulting search_manuals..." }` — fills the silent gap of the HTTP call to the agent. |
| `token`     | While the final answer is generated | `{ "type": "token", "text": "<chunk>" }` — one content chunk; concatenating all `token` events rebuilds the full answer. |
| `error`     | On a recoverable agent failure, or a fatal graph error | `{ "type": "error", "recoverable": true\|false, "message": "..." }` — once streaming has begun the status is already `200 OK`, so failures are delivered as events, not as HTTP error codes. |
| `citations` | Once, after the graph ends | `{ "type": "citations", "citations": [ ... ] }` — structured references accumulated from the tool artifacts, delivered separately from the token stream. |
| `done`      | Once, last | `{ "type": "done", "session_id": "<uuid>" }` — marks the end of the turn; the connection then closes. |

Consume it with `curl -N` (Swagger UI buffers the stream and only shows
it at the end, which defeats the purpose):

```bash
curl -N -X POST http://localhost:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "perché la macchina non parte", "machine_id": "2"}'
```

**Frontend note**: the browser's native `EventSource` only supports
`GET`. Since this endpoint is a `POST` (the question travels in the
body), the frontend must read the stream with `fetch` + `ReadableStream`
and parse the `event:`/`data:` frames manually, rather than using
`EventSource`.

## Requirements

- Python 3.12
- `langgraph`, `langchain-ollama`, `langfuse` (see `requirements.txt`)
- Ollama running locally, with model(s) pulled that support tool
  calling `gpt-oss:20b`. Currently the same
  model is used for both the orchestrator and the Manuals Agent
- The Manuals Agent running and reachable
- A reachable Langfuse instance (self-hosted via Docker Compose) for
  tracing; credentials provided via `.env` (see environment variables)

## Local setup

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate        # Linux
# .\venv\Scripts\Activate.ps1   # Windows PowerShell

pip install -r requirements.txt

cp .env.example .env
# edit .env if needed, in particular MANUALS_AGENT_URL, ORCHESTRATOR_OLLAMA_MODEL,
# ORCHESTRATOR_NUM_CTX, and the LANGFUSE_* credentials
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
**Terminal 3 - LangFuse**
```bash
follow the instruction "../langfuse-local/README"
```


Test the non-streaming endpoint with curl:
```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "perché la macchina non parte", "machine_id": "2"}'
```

or via `http://localhost:8000/docs`.

Test the streaming endpoint with `curl -N` (do **not** use Swagger for
this one — it buffers the stream):
```bash
curl -N -X POST http://localhost:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "perché la macchina non parte", "machine_id": "2"}'
```


**Note on visibility**: the manual `logger.info(...)` step-by-step
logging from iteration 2 was intentionally not carried over to the
LangGraph version — Langfuse now replaces it, providing a persistent,
navigable trace of each run. For quick ad-hoc inspection, a temporary
debug print inside `handle()` / `handle_stream()` still works.

## Environment variables (`.env`)

| Variable                       | Description                                            | Example                  |
|---------------------------------|-----------------------------------------------------------|---------------------------|
| `MANUALS_AGENT_URL`             | Base URL of the Manuals Agent service                     | `http://localhost:8001`  |
| `ORCHESTRATOR_LLM_PROVIDER`     | LLM provider used by the orchestrator                     | `ollama`                  |
| `ORCHESTRATOR_OLLAMA_BASE_URL`  | Base URL of the Ollama server for the orchestrator        | `http://localhost:11434` |
| `ORCHESTRATOR_OLLAMA_MODEL`     | Model used for routing/tool-calling (must support it)     | `gpt-oss:20b`             |
| `ORCHESTRATOR_NUM_CTX`          | Context window fixed explicitly (see `config.py` notes)   | `4096`                    |
| `ORCHESTRATOR_MAX_ITERATIONS`   | Max reason/act/observe cycles before giving up             | `5`                       |
| `LANGFUSE_PUBLIC_KEY`           | Langfuse public key (bridged into `os.environ`)           | `pk-lf-...`               |
| `LANGFUSE_SECRET_KEY`           | Langfuse secret key (bridged into `os.environ`)           | `sk-lf-...`               |
| `LANGFUSE_HOST`                 | Base URL of the self-hosted Langfuse instance             | `http://localhost:3000`  |
| `CHECKPOINT_DB_PATH`            | Path to the SQLite file holding conversation checkpoints  | `data/checkpoints.sqlite` |

## Known limitations / next steps

- **Checkpointing is durable but single-node** — the graph is compiled
  with an `AsyncSqliteSaver` writing to a SQLite file, so conversations
  survive a process restart. It is a local file, so it is not shared
  across multiple backend processes; a multi-node deployment would use
  `AsyncPostgresSaver` (out of scope for the thesis demo). Note that in a
  container the file must be on a mounted volume to survive an image
  rebuild. The next step is a `GET /v1/conversations/{id}/messages`
  history endpoint, which the checkpointer's `aget_state` makes almost
  free now that persistence is durable.
- **Same model used for both the orchestrator and the Manuals Agent**
  (`gpt-oss:20b`) — chosen for simplicity/VRAM-safety on 16GB hardware
  (no model-swapping), at the cost of using a heavier-than-necessary
  model for the lightweight routing task. Not yet benchmarked against a
  smaller dedicated orchestrator model on equal footing to isolate
  whether perceived slowdowns come from the model choice or the framework
  itself.
- **No automated evaluation of routing quality** — nothing currently
  measures whether the LLM's decision to stop (or keep calling tools)
  was actually correct; relies entirely on the system prompt and the
  model's own judgment. A `confidence`-based check or a separate judge
  step are possible future additions.
- **No authentication** on the `/v1/chat` and `/v1/chat/stream`
  endpoints yet.
- **Single agent registered** (`search_manuals`). Real multi-agent
  routing (IoT, Orders, Troubleshooting) is the next milestone — each
  new agent needs one client in `app/clients/` and one `@tool` function
  in `agent_registry.py`, nothing else.