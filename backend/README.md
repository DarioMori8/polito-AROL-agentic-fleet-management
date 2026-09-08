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
to a SQLite file on disk rather than kept in RAM. A **conversation
history endpoint** then reads any past conversation back from that
durable store for re-display.

Alongside the chat path, the backend owns a **domain database** holding
the customer fleet — companies, users, machine models, machines and their
manuals — modelled directly on the AROL Q2 synthetic dataset, and serves
it through read-only resource endpoints (see *Domain database* and *API*).

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
│   │       └── chat.py            # POST /v1/chat, POST /v1/chat/stream, GET /v1/conversations/{id}/messages
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── base.py                # Orchestrator ABC (interface/implementation decoupling)
│   │   ├── agent_registry.py      # LangChain @tool-decorated functions, one per agent
│   │   └── orchestrator.py        # LangGraphOrchestrator: StateGraph-based reason/act/observe loop
│   ├── clients/
│   │   ├── base.py                # Abstract interface for agent clients
│   │   ├── manuals_client.py      # HTTP client for the Manuals Agent
│   │   └── exceptions.py          # AgentUnavailableError (domain-level error)
│   ├── db/
│   │   ├── engine.py              # Async engine, session factory, create_all, FK pragma
│   │   ├── models.py              # SQLModel tables: Company, User, MachineModel, Machine, Manual
│   │   └── seed.py                # Fixture bootstrap + manual ingest from data/manuals
│   ├── models/
│   │   └── chat.py                # ChatRequest / ChatResponse (endpoint contract)
│   └── resources/
│       ├── repository.py          # Repository interfaces + DB-backed implementations
│       ├── router.py              # Read-only machine and manual endpoints
│       └── schemas.py             # MachineOut / ManualOut — the wire contract
│
├── data/
│   ├── manuals/                   # <serialNumber>_manual_<LANG>.pdf — source of truth for documentation
│   ├── domain.db                  # Domain database (SQLite)
│   └── checkpoints.sqlite         # LangGraph conversation checkpoints (separate DB)
├── requirements.txt
├── .env
├── .dockerignore
└── Dockerfile
```

## What each part does

### `app/main.py`
Creates the single FastAPI application instance, includes all routers,
and configures logging. Defines the **`lifespan`**: at startup it creates
the domain tables, runs the seed, opens the durable checkpointer and
compiles the graph (through `build_graph()`), wraps it in a
`LangGraphOrchestrator`, and places that on `app.state`; at shutdown the
checkpointer's SQLite connection is closed cleanly as the `async with`
unwinds. This is why the graph is an application resource created at
startup, not a module-level global.

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

It also holds the two storage paths, `DOMAIN_DB_PATH` and `MANUALS_DIR`.
Both are anchored to the location of `config.py` itself
(`Path(__file__).resolve().parent.parent / ...`) rather than being
relative to the process working directory: a working-directory-relative
path resolves differently depending on where `uvicorn` is launched from
and on the container's `WORKDIR`, and fails *silently* (the seed logs a
warning and registers zero manuals instead of raising). Both remain
overridable by environment variable.

### `app/api/v1/chat.py`
The HTTP-facing layer. Validates the incoming `ChatRequest` and
delegates entirely to the orchestrator — `handle(...)` for the
non-streaming endpoint, `handle_stream(...)` for the streaming one — and
serializes the streaming orchestrator's semantic events into the SSE
wire format (`event:`/`data:` frames). It also exposes the read-only
history endpoint, which calls `orchestrator.get_history(...)` and turns
a `None` result into a `404`. It contains no business logic and no
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
  Beyond the two chat entry points, the orchestrator exposes
  `get_history(session_id)`, which reads the persisted state via
  `aget_state` and **projects** it into a client-facing shape: it filters
  out the mechanical messages (the empty tool-call `AIMessage`, the raw
  `ToolMessage`), keeps only the human-visible turns as `user`/`assistant`
  entries, strips the internal `[machine_id: ...]` routing tag from user
  content, and re-attaches each turn's citations (which live in the tool
  artifact, not the answer) to that turn's assistant message. It returns
  `None` when the thread has no saved state, which the endpoint maps to a
  `404`.

### `app/clients/`
One client class per agent, each implementing a shared abstract
interface (`base.py`). A client's only job is to know how to talk to
one specific agent over HTTP — building the request, handling
timeouts/retries, and translating low-level `httpx` errors into a
single domain-level `AgentUnavailableError`. This isolates the
orchestrator from networking details entirely: if the transport layer
changes later (e.g. moving to MCP), only the client implementation
needs to change.

The shared HTTP client retries connection errors and connection timeouts
up to three times. It does not retry response timeouts, which could enqueue
duplicate inference while the original request is still running, or HTTP
error status codes. Connections time out after 5 seconds; the response timeout
is configurable with `AGENTS_REQUEST_TIMEOUT_SECONDS` (240 seconds by default)
to allow multiple local LLM calls per agent request.

### `app/db/`
- **`engine.py`** — the async engine (`sqlite+aiosqlite`), the session
  factory, and `create_db_and_tables()`. It also registers a `connect`
  event listener issuing `PRAGMA foreign_keys=ON`: **SQLite disables
  foreign keys by default, per connection**, so without this listener
  every FK and every `ON DELETE RESTRICT` in the schema is silently
  ignored — the constraints exist in the DDL but never fire.
- **`models.py`** — the five SQLModel tables (see *Domain database*).
- **`seed.py`** — populates the DB at startup. Idempotency is split in
  two, deliberately: **reference data** (companies, users, models,
  machines) is inserted only when the DB is empty, while **manuals are
  reconciled on every run** by scanning `MANUALS_DIR`. Dropping a new PDF
  into the folder and restarting is therefore enough to register it,
  without wiping anything. The current fixtures are placeholders for the
  XLSX bootstrap; only the eight serial numbers are real.

### `app/models/`
Pydantic schemas shared with the Agents project via the `contracts`
package (e.g. `SearchManualResponse`, `Citation`). `app/models/chat.py`
defines `ChatRequest`/`ChatResponse`, the contract for the chat
endpoints (not shared with the agents project, since it's
backend/frontend-specific). `ChatRequest.session_id` is optional —
absent on the first turn, echoed back by the client on subsequent turns
to continue the same conversation. It also defines the history contract:
`ConversationHistory` (a `session_id` plus a list of `HistoryMessage`),
`HistoryMessage` (a `role`, `content`, and always-present `citations`),
and the `MessageRole` enum (`user` / `assistant`).

### `app/resources/`
- **`repository.py`** — the data-access interfaces and their DB-backed
  implementations. `MachineRepository` exposes `list_machines`,
  `get_machine` (by primary key) and `get_machine_by_serial`;
  `ManualRepository` exposes `get_by_machine`, `get_by_filename` and
  `get_manual`. `get_by_machine` returns a single `Manual | None`, not a
  list, because the 1:1 relation is enforced by a UNIQUE constraint —
  returning a list would advertise a cardinality the schema forbids.
- **`schemas.py`** — the **wire** contract, deliberately distinct from
  the table models, because the two differ by *subtraction* and by
  *addition*. Subtraction: `Manual.storage_path` is a server-side
  filesystem path and must never travel over HTTP. Addition: `url` is not
  a column at all — it is derived from the route that serves the file, so
  it is composed in `ManualOut.from_model()`. Returning SQLModel tables
  directly would make every future column public by default; the client
  contract must be a decision, not a side effect of the schema.
- **`router.py`** — the read-only endpoints, plus the two dependency
  providers that pick the concrete repository implementation. This is the
  only module that reads `storage_path`, in the file-download endpoint.

## Domain database

A SQLite database (`DOMAIN_DB_PATH`) modelled on the AROL Q2 synthetic
fleet dataset. It is separate from the LangGraph checkpoint DB: one holds
the fleet, the other holds conversations, and they share nothing.

The backend owns the **identity layer** only — who the customers are,
which machines they own, and the manuals documenting them. Telemetry,
alarms, maintenance history, orders and quotes are treated as external
AROL services and are deliberately **not** stored here.

### Tables

| Table            | Key fields | Notes |
|------------------|-----------|-------|
| `companies`      | `id` (`CMP-001`), name, country, city, sector, currency, locale | The tenant boundary of the access model. |
| `users`          | `id` (`USR-001`), `company_id` → companies, first/last name, email, job title, `visibility` | `visibility` is a closed vocabulary: `full` / `technician` / `commercial`. |
| `machine_models` | `id` (`MDL-100`), model code, description, `primitive_diameter`, nominal heads, container/cap type, industry segment, notes | Catalogue-level specification, shared by many machines. `primitive_diameter` is the only nullable column. |
| `machines`       | `id` (`MCH-0001`), `company_id` → companies, `model_id` → machine_models, `serial_number` (UNIQUE), delivery date, plant location, configuration profile, `plc_family`, software version | The physical unit. `plc_family` is a closed vocabulary: `SIEMENS-SIMATIC-S7` / `LINE-PLC-INTEGRATED` / `HARDWIRED-CONTROL-PANEL`. |
| `manuals`        | `id` (UUID), `machine_id` → machines (UNIQUE), filename, `storage_path`, content type, size, uploaded at, language, title | One manual per machine, exactly. |

Design decisions worth knowing:

- **Two identifiers, two jobs.** `machine_id` is the surrogate primary
  key and the target of every foreign key: it exists only to identify,
  so it never needs to change. `serial_number` is the natural key from
  the outside world and is the **resolution** key — it is what a manual
  filename, a QR code or a machine plate carries. Hanging foreign keys
  off the serial would turn a typo correction into a migration; hence FK
  on the id, lookups on the serial. `serial_number` is UNIQUE precisely
  because resolution must be unambiguous.
- **1:1 between machines and manuals** is enforced by a UNIQUE constraint
  on `manuals.machine_id`, not merely assumed. A plain foreign key would
  allow N manuals per machine, which the dataset does not.
- **`ON DELETE RESTRICT` on every foreign key** — an existing company
  cannot be deleted while it still owns machines, a model cannot be
  deleted while units of it are installed.
- **Closed vocabularies are enforced by the database**, not only by
  Python: the enums are declared with `create_constraint=True`, which
  emits a SQL `CHECK`. Without it (SQLAlchemy's default since 1.4) the
  column is a plain `VARCHAR` and any write bypassing the ORM can store
  an invalid value.
- **No `status` column.** Runtime state is not an attribute of a machine;
  it is the latest reading of its telemetry stream, which belongs to an
  external service. The dataset's `operationalStatus` vocabulary has six
  values (`Running`, `Alarm`, `Idle`, `Stopped`, `Maintenance`,
  `Size change`), not the three of the earlier mock enum.
- **`delivery_date` is stored as a string**, faithful to the dataset; it
  is displayed, not computed on.

### Manual ingest

Manuals are not seeded by hand: `seed.py` scans `MANUALS_DIR` for files
named `<serialNumber>_manual_<LANG>.pdf`, extracts the serial, resolves
the owning machine through it, and registers the row with that machine's
`id`. The folder is the source of truth for documentation.

Serials come in **two shapes**, numeric (`17478`) and alphanumeric
(`A2055`), so the filename pattern must not assume digits — a `\d+`
serial group silently drops half the fleet, with no error and no manual
registered for those machines.

Files that do not match the pattern, and files whose serial matches no
machine, are skipped with a warning rather than aborting the seed.

## API

The backend exposes chat endpoints (streaming and non-streaming), a
conversation history endpoint, read-only resource endpoints for machines
and manuals, and a health check. The two chat endpoints accept the
**same** request body and delegate entirely to the orchestrator; they
differ only in how the answer is delivered — one JSON block versus
token-by-token.

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
{ "query": "perché la macchina non parte", "machine_id": "MCH-0004" }
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
  "citations": [{ "doc": "17478_manual_EN.pdf", "page": 12, "snippet": "..." }],
  "session_id": "3f2c1a9e-8b7d-4e6f-a1c2-9d8e7f6a5b4c"
}
```

> **Cross-service contract**: `Citation.doc` must be the same string
> stored in `manuals.filename` (`<serialNumber>_manual_<LANG>.pdf`), or
> the frontend cannot resolve a citation back to a manual row. This is
> the agreement to keep aligned with the agents service — a mismatch
> breaks the link with no error on either side.

### `GET /v1/conversations/{session_id}/messages`

Conversation history — re-reads a past conversation from the durable
checkpointer for re-display (e.g. the frontend reopening a machine's
chat). Receives a `session_id` in the path and returns that
conversation's messages, projected for the client: internal mechanics
(empty tool-call messages, raw tool results) are removed, the
`[machine_id: ...]` routing tag is stripped from user messages, and each
answer's citations are attached to it.

**Returns** — `ConversationHistory`:

| Field        | Type                  | Description |
|--------------|-----------------------|-------------|
| `session_id` | `str`                 | The conversation id (echoed from the path). |
| `messages`   | `list[HistoryMessage]`| The projected conversation, in order. |

Each `HistoryMessage` has `role` (`user` / `assistant`), `content`, and
`citations` (a list of `{ doc, page, snippet }`, always present — empty
for user messages and for answers with no references).

Responds `404` if no conversation with that id exists (an unknown
`session_id` has no saved state; there is no such thing as a real
conversation with zero messages).

```json
{
  "session_id": "3f2c1a9e-8b7d-4e6f-a1c2-9d8e7f6a5b4c",
  "messages": [
    { "role": "user", "content": "come faccio la manutenzione?", "citations": [] },
    { "role": "assistant", "content": "Ecco la procedura...", "citations": [
      { "doc": "17478_manual_EN.pdf", "page": 12, "snippet": "..." }
    ]}
  ]
}
```

### `GET /v1/machines`

Fleet list. Takes no input.

**Returns**: a JSON array of `MachineOut` objects, each with `id`,
`company_id`, `model_id`, `serial_number`, `delivery_date`,
`plant_location`, `configuration_profile`, `plc_family` and
`software_version`. An empty array is a valid response.

> **Known gap**: this endpoint has **no tenant filter** and currently
> returns every company's fleet. `company_id` is meant to be a boundary
> that is never crossed; closing this requires an authenticated user to
> take the `company_id` from. See *Known limitations*.

### `GET /v1/machines/{machine_id}`

Machine detail — the landing target of the QR-scan use case. Receives a
machine id in the path and returns that single machine's record.

**Returns**: one `MachineOut`. Responds `404` if no machine with that id
exists. The id space is shared with the chat endpoint's `machine_id`, so
the same identifier addresses a machine everywhere in the system.

### `GET /v1/machines/by-serial/{serial_number}`

Machine detail by **serial number** — the identifier printed on the
machine itself. This is the entry point for the QR-code URL form that
carries a serial rather than an id, and for resolving a manual filename
(or an agent citation) back to a machine.

**Returns**: one `MachineOut`. Responds `404` if no machine carries that
serial. No routing conflict with `/v1/machines/{machine_id}`: that route
has two path segments, this one has three, so they can never match the
same URL.

### `GET /v1/machines/{machine_id}/manual`

The manual of a machine. **Singular, and returns an object rather than an
array** — a machine has at most one manual, enforced by a UNIQUE
constraint.

**Returns**: one `ManualOut`. Two distinct `404`s, deliberately: *machine
not found* and *no manual registered for this machine* are different
failures pointing at different causes (a wrong id versus an ingest that
did not link the PDF).

### `GET /v1/manuals/{manual_id}`

Manual detail. Receives a manual id (a UUID) in the path.

**Returns**: one `ManualOut`, with `id`, `machine_id`, `title`,
`filename`, `language`, `content_type`, `size`, `uploaded_at` and `url`.
Responds `404` if no manual with that id exists.

`url` is the relative path of the download endpoint below — the client
follows it rather than constructing it. `storage_path` is never exposed.

```json
{
  "id": "a71d2c59-f6dd-4848-a8fc-5e6a1ffcc86d",
  "machine_id": "MCH-0004",
  "title": "Use & Maintenance Manual",
  "filename": "17478_manual_EN.pdf",
  "language": "en",
  "content_type": "application/pdf",
  "size": 18682784,
  "uploaded_at": "2026-08-11T16:06:03.840731",
  "url": "/v1/manuals/a71d2c59-f6dd-4848-a8fc-5e6a1ffcc86d/file"
}
```

### `GET /v1/manuals/{manual_id}/file`

The PDF itself, streamed with `FileResponse` and a `Content-Disposition`
carrying the original filename.

**Returns**: the file bytes, `Content-Type: application/pdf`. Responds
`404` both when the manual row does not exist and when the row exists but
the file is missing on disk — the second case is a real one (an unmounted
volume, a moved file) and is reported as a clean `404` rather than a
`500`.

```bash
curl -s localhost:8000/v1/machines/MCH-0004/manual | python3 -m json.tool
URL=$(curl -s localhost:8000/v1/machines/MCH-0004/manual \
      | python3 -c "import json,sys; print(json.load(sys.stdin)['url'])")
curl -s -o /tmp/m.pdf -w "%{http_code} %{content_type} %{size_download}\n" "localhost:8000$URL"
```

### `POST /v1/chat/stream`

Streaming chat over **Server-Sent Events (SSE)**. Receives the same
`ChatRequest`, but instead of returning one JSON object it keeps the HTTP
response open and streams a sequence of typed events as the graph
executes (`graph.astream`), so the frontend can render the answer as it
forms. The question travels in the request body; the whole answer
streams back on the same connection.

**Receives**: identical to `POST /v1/chat` (`query`, `machine_id`,
optional `session_id`).

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
  -d '{"query": "perché la macchina non parte", "machine_id": "MCH-0004"}'
```

**Frontend note**: the browser's native `EventSource` only supports
`GET`. Since this endpoint is a `POST` (the question travels in the
body), the frontend must read the stream with `fetch` + `ReadableStream`
and parse the `event:`/`data:` frames manually, rather than using
`EventSource`.

## Requirements

- Python 3.12
- `langgraph`, `langchain-ollama`, `langfuse`, `sqlmodel`, `aiosqlite`
  (see `requirements.txt`)
- Ollama running locally, with model(s) pulled that support tool
  calling `gpt-oss:20b`. Currently the same
  model is used for both the orchestrator and the Manuals Agent
- The Manuals Agent running and reachable
- A reachable Langfuse instance (self-hosted via Docker Compose) for
  tracing; credentials provided via `.env` (see environment variables)
- The manual PDFs present in `data/manuals/`, named
  `<serialNumber>_manual_<LANG>.pdf`

## Local setup

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate        # Linux
# .\venv\Scripts\Activate.ps1   # Windows PowerShell

pip install -r requirements.txt

cp .env.example .env
# edit .env if needed, in particular AGENTS_SERVICE_URL, ORCHESTRATOR_OLLAMA_MODEL,
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

**Terminal 3 — LangFuse**
```bash
follow the instruction "../langfuse-local/README"
```

Test the non-streaming endpoint with curl:
```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "perché la macchina non parte", "machine_id": "MCH-0004"}'
```

or via `http://localhost:8000/docs`.

Test the streaming endpoint with `curl -N` (do **not** use Swagger for
this one — it buffers the stream):
```bash
curl -N -X POST http://localhost:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "perché la macchina non parte", "machine_id": "MCH-0004"}'
```

### Verifying the domain DB

The seed logs one line per registered manual; eight lines means every PDF
resolved to a machine. Zero lines plus a *Manuals directory not found*
warning means the path or the volume mount is wrong, not the DB.

```bash
docker compose logs backend | grep -iE "seed|manual|Traceback"
```

The container image has no `sqlite3` CLI, so inspect the DB through
Python. The join below is the useful one: it shows the whole fleet with
its manual, and a `LEFT JOIN` makes a missing manual visible instead of
hiding the row.

```bash
docker compose exec -T backend python - <<'EOF'
import sqlite3
from app.config import settings
con = sqlite3.connect(str(settings.DOMAIN_DB_PATH))
for t in ("companies","users","machine_models","machines","manuals"):
    print(f"{t:15s}", con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
for r in con.execute("""
    SELECT m.id, m.serial_number, c.name, mm.model_code,
           COALESCE(mn.filename, '*** MISSING ***')
    FROM machines m
    JOIN companies c       ON c.id  = m.company_id
    JOIN machine_models mm ON mm.id = m.model_id
    LEFT JOIN manuals mn   ON mn.machine_id = m.id
    ORDER BY m.id"""):
    print(" ", r)
EOF
```

**Note on visibility**: the manual `logger.info(...)` step-by-step
logging from iteration 2 was intentionally not carried over to the
LangGraph version — Langfuse now replaces it, providing a persistent,
navigable trace of each run. For quick ad-hoc inspection, a temporary
debug print inside `handle()` / `handle_stream()` still works.

## Environment variables (`.env`)

| Variable                       | Description                                            | Example                  |
|---------------------------------|-----------------------------------------------------------|---------------------------|
| `AGENTS_SERVICE_URL`           | Base URL of the shared agents service (Manuals, Docs, IoT) | `http://localhost:8001`  |
| `AGENTS_REQUEST_TIMEOUT_SECONDS` | Response timeout for agent requests, in seconds          | `240`                    |
| `ORCHESTRATOR_LLM_PROVIDER`     | LLM provider used by the orchestrator                     | `ollama`                  |
| `ORCHESTRATOR_OLLAMA_BASE_URL`  | Base URL of the Ollama server for the orchestrator        | `http://localhost:11434` |
| `ORCHESTRATOR_OLLAMA_MODEL`     | Model used for routing/tool-calling (must support it)     | `gpt-oss:20b`             |
| `ORCHESTRATOR_NUM_CTX`          | Context window fixed explicitly (see `config.py` notes)   | `16384`                   |
| `ORCHESTRATOR_MAX_ITERATIONS`   | Max reason/act/observe cycles before giving up             | `5`                       |
| `LANGFUSE_PUBLIC_KEY`           | Langfuse public key (bridged into `os.environ`)           | `pk-lf-...`               |
| `LANGFUSE_SECRET_KEY`           | Langfuse secret key (bridged into `os.environ`)           | `sk-lf-...`               |
| `LANGFUSE_HOST`                 | Base URL of the self-hosted Langfuse instance             | `http://localhost:3000`  |
| `CHECKPOINT_DB_PATH`            | Path to the SQLite file holding conversation checkpoints  | `data/checkpoints.sqlite` |
| `DOMAIN_DB_PATH`                | Path to the SQLite file holding the fleet domain DB       | `data/domain.db`          |
| `MANUALS_DIR`                   | Directory scanned for manual PDFs at seed time            | `data/manuals`            |

## Docker notes

- **Mount `data/` as a volume.** Both SQLite files and the manual PDFs
  live there; without a volume the DB is recreated on every container
  rebuild, and the manuals are baked into the image (so adding one
  requires a rebuild).
- **`create_all` does not migrate.** It creates missing tables and leaves
  existing ones untouched, so a schema change requires deleting the
  domain DB file — never the checkpoint DB, which is unrelated.
- **The image copies the source in.** Editing a file on the host without
  `docker compose up -d --build backend` leaves the old code running; if
  a change seems not to take effect, check the routes the app actually
  declares with `curl -s localhost:8000/openapi.json`.

## Known limitations / next steps

- **`MachineOut` exposes `model_id`, not a readable model name** — a
  client showing `MDL-100` to an operator is not useful. Either a
  separate models endpoint (two calls, clean separation) or denormalizing
  `model_code`/`description` into `MachineOut` via a join.
- **`page_count` is not available** on manuals; it would require parsing
  each PDF at ingest time and a new column.
- **Checkpointing is durable but single-node** — the graph is compiled
  with an `AsyncSqliteSaver` writing to a SQLite file, so conversations
  survive a process restart. It is a local file, so it is not shared
  across multiple backend processes; a multi-node deployment would use
  `AsyncPostgresSaver` (out of scope for the thesis demo). Note that in a
  container the file must be on a mounted volume to survive an image
  rebuild.
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
- **No authentication** on any endpoint yet. The history endpoint is
  structured so an ownership check ("does the caller own this thread?")
  can slot in between receiving the `session_id` and reading the data,
  without touching the read or the projection. Binding conversations to
  an authenticated user (for a "my conversations" list) additionally
  needs a user→thread_id registry, which the checkpointer does not
  provide.
- **Single agent registered** (`search_manuals`). Real multi-agent
  routing (IoT, Orders, Troubleshooting) is the next milestone — each
  new agent needs one client in `app/clients/` and one `@tool` function
  in `agent_registry.py`, nothing else.