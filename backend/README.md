# AROL Customer Platform — Backend & Orchestrator

Backend service that exposes the API consumed by the frontend: session-based
authentication, the chat API, and read-only resources (machines and manuals).
Chat requests are handled by an LLM-based orchestrator built on **LangGraph**,
which routes each question to the specialized AI Agents (Manuals, Docs, IoT).

The orchestrator's reason -> act -> observe loop is a compiled **LangGraph**
`StateGraph`: an LLM reading tool descriptions decides which agent(s) to call,
`ToolNode` executes the calls (in parallel when there are several), and
`tools_condition` loops back to the model until it answers in plain text.
On top of the loop:

- **Langfuse tracing** — a callback per graph invocation, with W3C trace context
  propagated over HTTP to the agents. Each turn has one trace containing the
  orchestrator and agent operations; turns are grouped by user and conversation.
- **Token-by-token streaming** of the answer over Server-Sent Events.
- **Ollama tool-parser recovery** — if Ollama rejects a generated tool call
  after this turn has collected tool results, synthesize once without tool
  schemas, using those same results. The failed generation and the named
  `orchestrator.final_synthesis_recovery` attempt both remain in Langfuse.
  Streaming clients receive `reset` before replacement tokens, so partial
  output from the failed attempt is not appended to the final answer.
- **Durable checkpointing** — the graph is compiled with an `AsyncSqliteSaver`,
  so turns sharing a `thread_id` accumulate into one conversation that
  survives a process restart. A **history endpoint** reads it back.
- **Session-based authentication** — an opaque token in an `HttpOnly` cookie,
  resolved server-side on every request.
- **Multi-tenancy** — every read is scoped to the authenticated user's
  company; every conversation is owned by one user and pinned to one machine.
- **Guest access by QR code** — someone in the plant who scans a machine's QR
  without an account is logged in as their company's guest and can read
  manuals only (see *Guest access*).
- **Visibility-based access** — inside their company, a user reaches only
  the data domains their `visibility` allows, enforced in code before any
  agent is contacted (see *Access model*).

Alongside the chat path, the backend owns a **domain database** holding the
customer fleet — companies, users, machine models, machines, their manuals —
plus the authentication sessions and the ownership record of each
conversation. It is modelled directly on the AROL Q2 synthetic dataset.

```
Frontend (browser, cookie-authenticated)
    → Backend API
        /v1/sessions            login / whoami / logout
        /v1/machines, /v1/manuals   tenant-scoped resources
        /v1/chat, /v1/chat/stream   → Orchestrator (LangGraphOrchestrator)
            1. prepare_turn: machine ∈ user's company? thread owned by user?
            2. StateGraph: agent node (ChatOllama + bound tools)
                --(tool_calls?)--> tools node (ToolNode)
                    → ManualsClient → Manuals Agent  (RAG on Chroma)
                    → DocsClient    → Docs Agent     (quotes, orders)
                    → IoTClient     → IoT Agent      (telemetry, alarms, tickets)
                <-- loops back to agent node until plain-text response
```

## Project structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app, lifespan, CORS, routers, logging
│   ├── config.py                  # Settings (pydantic-settings) + Langfuse env bridge
│   ├── api/
│   │   ├── deps.py                # get_current_user / CurrentUser: the auth gate
│   │   └── v1/
│   │       ├── auth.py            # POST/GET/DELETE /v1/sessions[/current]
│   │       └── chat.py            # /v1/chat, /v1/chat/stream, /v1/conversations[/{id}/messages]
│   ├── orchestrator/
│   │   ├── base.py                # Orchestrator ABC, TurnContext, domain errors
│   │   ├── agent_registry.py      # @tool functions, one per agent; scope injected via config
│   │   └── orchestrator.py        # LangGraphOrchestrator: graph, streaming, history
│   ├── clients/
│   │   ├── base.py                # HttpAgentClient: shared transport, retry, validation
│   │   ├── manuals_client.py      # Manuals Agent client
│   │   ├── docs_client.py         # Docs Agent client (carries company_id)
│   │   ├── iot_client.py          # IoT Agent client
│   │   └── exceptions.py          # AgentUnavailableError
│   ├── security/
│   │   ├── access.py              # Access model: visibility -> allowed data domains
│   │   ├── passwords.py           # scrypt hashing / verification
│   │   └── session.py             # authenticate, create/resolve/destroy session
│   ├── db/
│   │   ├── engine.py              # Async engine, session factory, SQLite PRAGMAs, create_all
│   │   ├── models.py              # SQLModel tables (see Domain database)
│   │   ├── guest_accounts.py      # Guest passwords, QR URLs; CLI for rotation
│   │   └── seed.py                # Dataset fixtures, dev credentials, manual ingest
│   ├── models/
│   │   ├── auth.py                # LoginRequest / UserOut
│   │   └── chat.py                # ChatRequest / ChatResponse / ConversationHistory
│   └── resources/
│       ├── repository.py          # Tenant-scoped repository interfaces + DB implementations
│       ├── router.py              # Machine and manual endpoints
│       └── schemas.py             # MachineOut / ManualOut — the wire contract
│
├── data/                          # created at startup, persisted by the bind mount
│   ├── domain.sqlite              # Domain database (+ -wal / -shm side files)
│   ├── qr_urls.txt                # QR URLs with live guest passwords (mode 0600, never commit)
│   └── checkpoints.sqlite         # LangGraph conversation checkpoints (separate DB)
├── requirements.txt
├── .env
├── .dockerignore
└── Dockerfile
```

The manual PDFs are **not** under `backend/`: they live in `data/manuals/` at
the **root of the monorepo**, shared with the agents service, and are mounted
read-only at `/data/manuals` in both containers.

## What each part does

### `app/main.py`
Creates the FastAPI application, configures logging, CORS and the routers.
The **`lifespan`** creates the domain tables, runs the seed, opens the durable
checkpointer and compiles the graph (`build_graph()`), wraps it in a
`LangGraphOrchestrator` and stores it on `app.state`; at shutdown the
checkpointer connection closes as the `async with` unwinds and the engine's
pooled connections are disposed.

There is intentionally **no `StaticFiles` mount** for the manuals: a static
mount would serve any PDF to anyone who guesses a filename, bypassing both
authentication and tenant scoping. PDFs are served only through
`GET /v1/manuals/{id}/file`.

CORS lists the frontend origins explicitly with `allow_credentials=True`:
the browser only sends the session cookie cross-origin under that
combination, and a wildcard origin is not allowed with credentials.

### `app/config.py`
A single typed source of configuration. Resolution order for every field:
process environment (docker-compose `environment:`) > `backend/.env` > the
default in the class. Fields without a default (`ORCHESTRATOR_OLLAMA_MODEL`,
the two Langfuse keys) are mandatory: if missing, the app refuses to start.

Defaults target **local** development (everything on `localhost`); inside
Docker every network address is overridden by the compose file, because in a
container `localhost` is the container itself. `ORCHESTRATOR_LLM_PROVIDER` is
a `Literal["ollama"]`, so an unsupported value fails validation instead of
being silently ignored. `ORCHESTRATOR_NUM_CTX` fixes the context window
explicitly: a mismatch can push VRAM usage past what is available and force
CPU offload (5-30x slowdown) — check with `ollama ps` (`PROCESSOR` should read
`100% GPU`).

All paths, including the `.env` file itself, are anchored to the location of
`config.py`, never to the working directory, so they resolve the same way
whatever directory `uvicorn` is launched from.

The module ends with a bridge into `os.environ` for the Langfuse credentials:
Langfuse's `CallbackHandler` reads them from the process environment, while
pydantic-settings reads `.env` into the model without exporting it.
`setdefault` never overwrites, so in Docker (where the variables are real) the
bridge is a no-op.

### `app/api/`
- **`deps.py`** — `get_current_user` reads the session cookie and resolves it
  through `security/session.py`; a missing, unknown or expired session fails
  with `401` before the endpoint runs. `CurrentUser` is the annotated alias
  endpoints and dependencies declare.
- **`v1/auth.py`** — the session as a resource: login creates it (and sets
  the cookie), `GET /current` reads it, logout deletes it.
- **`v1/chat.py`** — the chat endpoints. A turn runs in **two phases**:
  1. `prepare_turn` runs in the endpoint body, **before** any response is
     started, so its failures are real HTTP status codes (`404`);
  2. the graph runs inside the SSE generator, which starts only after `200`
     and the headers have been sent — from there on a failure can only be an
     `error` event.

  The orchestrator is obtained through a `get_orchestrator` dependency (not
  read from `app.state` inline) so tests can replace it.

### `app/orchestrator/`
- **`base.py`** — the contract between the HTTP layer and the engine:
  `prepare_turn(user, request) -> TurnContext`, `handle(context, query)`,
  `handle_stream(context, query)`, `get_history(user, thread_id)`. It also
  defines the domain errors `MachineNotFoundError` and
  `ConversationNotFoundError`: the orchestrator says *what* went wrong, the
  HTTP layer decides the status code, so the orchestrator stays free of
  FastAPI.
- **`agent_registry.py`** — one `@tool(response_format="content_and_artifact")`
  function per agent: `search_manuals`, `search_docs`, `search_iot`. `content`
  (a JSON string) is what the LLM reads; `artifact` (a dict) is what the
  orchestrator reads back to extract sources — a plain `@tool` would silently
  break source extraction. **The only argument the LLM controls is the
  query**: `machine_id` and `company_id` are injected through the
  `RunnableConfig` parameter, which LangChain hides from the tool schema, so
  the model can neither set, widen nor forge the scope. The manuals tool asks
  the model to rewrite the query **in English with the manual's technical
  terms**, because the manuals are English and searched semantically. Adding
  an agent means one client and one `@tool` function here.
- **`orchestrator.py`** — `LangGraphOrchestrator`.
  - `prepare_turn` checks that the machine belongs to the user's company
    (through the tenant-scoped repository) and, for an existing thread, that
    it belongs to the user and to that same machine; for a new thread it
    mints a UUID and records ownership in the `conversations` table.
  - `handle` runs the graph to completion (`ainvoke`); `handle_stream` runs it
    with `astream(stream_mode=["messages", "updates"])` and yields semantic
    events. Because of checkpointing, the graph result holds the **whole**
    thread: sources are taken only from the current turn (from the last
    `HumanMessage` on).
  - `get_history` returns `None` both for an unknown thread and for another
    user's thread (the caller cannot tell the two apart), then **projects**
    the checkpoint into a client view: tool-call messages and raw tool
    results are dropped, and each answer carries the sources of its turn.
  - `normalize_artifact` turns every tool artifact into a flat list of
    sources with a `kind` discriminator (`manual`, `document`, `order`,
    `quote`, `health`, `telemetry`, `alarms`, `maintenance`); exact
    duplicates are removed (an agent with its own internal loop may return
    the same citation once per internal search).
  - `recursion_limit` counts node executions: `ORCHESTRATOR_MAX_ITERATIONS * 2 + 1`.
  - The system prompt is prepended at call time, never stored in the state,
    so it does not accumulate across turns and a prompt change applies to old
    conversations too. It defines four routing actions (ROUTE / CLARIFY /
    CHITCHAT / DECLINE), requires answering in the user's language, and
    forbids any technical content, quotation or page number that is not in a
    tool result.

### `app/clients/`
`HttpAgentClient[T]` holds the whole transport: POST with retry, mapping of
every failure onto `AgentUnavailableError`, and validation of the response
against the shared `contracts` schema. Concrete clients only declare the
endpoint path, the response schema and a display name. The retry (tenacity)
covers **only** the raw network call and only transient errors (timeout,
connection refused): an HTTP error status is a real answer, not a glitch, and
retrying a higher-level method would repeat parsing and tracing side effects.
A malformed response body is reported as `AgentUnavailableError` too, so a
misbehaving agent never crashes the graph. `DocsClient` is the one whose task
carries a tenant: it takes `company_id` as a keyword-only argument.

### `app/security/`
- **`passwords.py`** — scrypt with a per-user random salt; verification uses
  `hmac.compare_digest` (constant time).
- **`session.py`** — the server-side half of session auth.
  - The cookie carries a random 256-bit token; the database stores only its
    **SHA-256 digest**, so a copy of the DB yields no usable session. A fast
    hash is enough here, unlike passwords: the token cannot be brute-forced.
  - `authenticate` returns one result for every failure (unknown email, no
    password, wrong password) and verifies against a dummy hash when the
    email is unknown, so neither the answer nor its timing reveals which
    addresses exist. scrypt runs in a worker thread, off the event loop.
  - Sessions have an 8-hour **idle** timeout with a sliding window; the
    deadline is rewritten only when it moves by at least 5 minutes, to avoid
    one SQLite write per request. Expired sessions are deleted, not just
    rejected.
  - Emails are compared **case-sensitively**, by design.

### `app/db/`
- **`engine.py`** — the async engine (`sqlite+aiosqlite`), the session
  factory (`expire_on_commit=False`: async SQLAlchemy forbids the implicit
  reload an expired object would trigger), `create_db_and_tables()` (which
  first creates the data directory) and the `get_session` dependency (one DB
  session per request, shared by every dependency of that request). A
  `connect` listener sets three PRAGMAs on every new connection:
  `foreign_keys=ON` (off by default in SQLite: without it every FK and every
  `ON DELETE` rule is silently ignored), `journal_mode=WAL` (readers and the
  writer no longer block each other) and `busy_timeout=5000` (wait for the
  write lock instead of failing with *database is locked*).
- **`models.py`** — the tables (see *Domain database*) and `UTCDateTime`, a
  column type that normalises datetimes to UTC on write, rejects naive ones,
  and re-attaches UTC on read (SQLite stores no timezone).
- **`seed.py`** — runs at every startup, idempotently. **Reference data**
  (transcribed from `AROL_Q2_synthetic_fleet_dataset.xlsx`, the same workbook
  the mock-backoffice serves) is inserted only on an empty DB; **credentials**
  (the shared dev password `Arol2026!`) are given to users that have none;
  **manuals** are reconciled on every run by scanning `MANUALS_DIR`.

### `app/models/`
Request/response contracts of the backend's own API (not shared with the
agents, which use the `contracts` package): `LoginRequest`/`UserOut`, and
`ChatRequest`/`ChatResponse`/`ConversationHistory`/`HistoryMessage`/`MessageRole`.
`ChatRequest.query` is stripped and must be 1-2000 characters;
`thread_id` is a UUID (anything else is a `422`).

### `app/resources/`
- **`repository.py`** — **tenant-scoped** repositories: `company_id` is fixed
  in the constructor and every query starts from a base query already
  filtered by it, so no method can "forget" the tenant. Manuals have no
  `company_id` of their own and are scoped through a join with their machine.
  A row of another company comes back as `None`, exactly like a missing one.
  Primary-key lookups use a filtered `select`, not `session.get`, because a
  PK lookup cannot carry the tenant condition.
  `MachineRepository`: `list_all`, `get`, `get_by_serial`.
  `ManualRepository`: `get`, `get_by_machine`, `get_by_filename`.
- **`schemas.py`** — the **wire** contract, distinct from the tables by
  *subtraction* (`storage_path` never leaves the process) and by *addition*
  (`url`, a `computed_field` derived from the id).
- **`router.py`** — the endpoints and the two dependency providers, which
  take `company_id` from `CurrentUser`: since every endpoint depends on a
  provider, every endpoint is authenticated without declaring it.

## Access model

Two independent checks, both required before any data is returned:

1. **`company_id`** — the tenant boundary, never crossed. Resource queries
   are scoped by it; agent calls receive it from the server.
2. **`visibility`** — narrows *what kind* of data a user sees inside their
   own company:

| visibility   | Identity & documentation (`search_manuals`, machines, manuals) | Operational (`search_iot`) | Commercial (`search_docs`) |
|--------------|:---:|:---:|:---:|
| `full`       | yes | yes | yes |
| `technician` | yes | yes | no  |
| `commercial` | yes | no  | yes |
| `guest`      | yes (no chat) | no | no |

The policy lives in one place, `app/security/access.py`. It is enforced
**in code, never by the LLM**:

- All tools stay visible to the model, which may call any of them. Each tool
  checks its data domain against the user's `visibility` (injected by the
  server through the `RunnableConfig`, like the tenant) **before** any HTTP
  call: a call outside the profile never reaches the agent.
- The refused tool returns an explicit denial, never an empty result (which
  would read as "no data exists"). The model is instructed to tell the user
  the information is outside their profile; independently of its wording,
  the stream emits a `denied` event and the responses carry a `denied` list.
- The check fails closed: a missing or unknown visibility allows nothing.
- `visibility` is read from the DB on every turn, so a role change applies
  from the next message. Tool results already in a thread's history are not
  retroactively removed.
- The enforcement point is the backend: it holds only if the agents service
  and the mock-backoffice are reachable from the backend alone (see *Docker
  notes*).

## Guest access

A guest is someone physically in the customer's plant who scans the QR code
on a machine **without having an account**. The frontend logs them in
automatically and shows that machine's manual.

- **One guest account per company** (`guest@<company domain>`, ids `USR-G001`…),
  with `visibility = guest`. They are not in the dataset; the seed adds them.
- **The QR carries the guest's credentials**:
  `<GUEST_QR_BASE_URL>/<machine_id>?u=<guest email>&k=<guest password>`. If no
  session exists, the frontend calls the ordinary `POST /v1/sessions` with
  them; a user already logged in keeps their own session.
- **Each company has its own random password.** A shared one would let the QR
  of one company open every other company's guest (guest emails are
  guessable), crossing the tenant boundary.
- **Only the hash is stored**, as for every password. The clear passwords
  exist only when minted: the seed writes one QR URL per machine to
  `backend/data/qr_urls.txt` (mode `0600`, keep it out of git). If the file is
  lost, rotate and reprint.
- **What a guest can do**, enforced in code:
  - tenant: only their own company, as for every user;
  - `visibility = guest` allows only machine identity and documentation;
  - the assistant is closed to guests: chat, stream and history answer `403`.

  "Only the scanned machine's manual" is enforced by the **frontend**: the
  backend lets a guest read the identity and manuals of every machine of
  their company, which the access model allows to every user of that company.
- **Rotation**, e.g. if a photo of a QR circulates: a new password for that
  company's guest; all of that company's QR codes must be reprinted. Existing
  guest sessions remain valid until they expire.

```bash
docker compose exec backend python -m app.db.guest_accounts rotate CMP-001
```

## Domain database

A SQLite database (`DOMAIN_DB_PATH`) modelled on the AROL Q2 synthetic fleet
dataset, separate from the LangGraph checkpoint DB. The backend owns the
**identity layer** — who the customers are, who their users are, which
machines they own, the manuals documenting them — plus authentication
sessions and conversation ownership. Telemetry, alarms, maintenance, orders
and quotes belong to external services (the mock-backoffice, reached through
the agents) and are **not** stored here.

### Tables

| Table            | Key fields | Notes |
|------------------|-----------|-------|
| `companies`      | `id` (`CMP-001`), name, country, city, sector, currency, locale | The tenant boundary. |
| `users`          | `id` (`USR-001`), `company_id` → companies, first/last name, `email` (UNIQUE), job title, `visibility`, `password_hash`, `salt` | `visibility` ∈ `full` / `technician` / `commercial` / `guest` (`guest` only for the seeded `USR-G…` accounts). Hash and salt are nullable: the dataset ships people, not credentials. |
| `machine_models` | `id` (`MDL-100`), model code, description, `primitive_diameter`, nominal heads, container/cap type, industry segment, notes | Catalogue-level specification. `primitive_diameter` is NULL for the single-head turrets. |
| `machines`       | `id` (`MCH-0001`), `company_id` → companies, `model_id` → machine_models, `serial_number` (UNIQUE), `delivery_date` (date), plant location, configuration profile, `plc_family`, `software_version` | The physical unit. `plc_family` ∈ `SIEMENS-SIMATIC-S7` / `LINE-PLC-INTEGRATED` / `HARDWIRED-CONTROL-PANEL`. `software_version` is NULL when the machine has none. |
| `manuals`        | `id` (UUID), `machine_id` → machines (UNIQUE), `filename` (UNIQUE), `storage_path`, content type, size, uploaded at, language, title | One manual per machine, exactly. |
| `sessions`       | `id` (SHA-256 of the token), `user_id` → users, created at, expires at | Model class `AuthSession`, to stay distinct from DB sessions and chat threads. |
| `conversations`  | `thread_id` (UUID), `user_id` → users, `machine_id` → machines, `preview`, created at | Ownership of a chat thread; the messages themselves live in the checkpoint DB. `preview` is the start of the first question (max 120 chars), stored at creation so a list is one query. |

Design decisions worth knowing:

- **Two identifiers, two jobs.** `machine_id` is the primary key and the
  target of every foreign key; `serial_number` is the natural key from the
  outside world (manual filename, QR code, plate) and the **resolution** key.
  Both are UNIQUE because resolution must be unambiguous.
- **Natural keys from the dataset** (`CMP-…`, `USR-…`, `MCH-…`) are kept as
  primary keys because they are shared with the mock-backoffice and the
  agents; `manuals` uses a surrogate UUID because the file has no external id.
- **Delete rules follow meaning**: `RESTRICT` on the domain data (a company
  that still owns machines cannot disappear); `CASCADE` from `users` to
  `sessions` and `conversations` (without an owner they are garbage).
- **Closed vocabularies are enforced by the database** (`create_constraint=True`
  emits a SQL `CHECK`), not only by Python.
- **Absence is `NULL`**, never a sentinel string such as `'n/a'`.
- **No `status` column** on machines: runtime state is the latest telemetry
  reading, owned by the IoT agent.
- **The two databases are not linked by a real foreign key** (they are
  separate files): deleting a `conversations` row does not delete its
  checkpoints.

### Manual ingest

`seed.py` scans `MANUALS_DIR` for `<serialNumber>_manual_<LANG>.pdf`,
resolves the owning machine through the serial, and registers the row with
that machine's `id`. Serials are numeric (`17478`) or alphanumeric (`A2055`),
so the pattern must not assume digits. Non-matching files and unknown serials
are skipped with a warning. This registers the files for **download**; the
**search index** (Chroma) is built separately by the agents service — see
`agents/README.md`, step 9.

## API

All endpoints except `/health` and `POST /v1/sessions` require the session
cookie; without it they answer `401`. A resource or conversation that belongs
to someone else answers `404`, exactly like a missing one — `403` would
confirm that the id exists.

### `GET /health`
Liveness probe (used by the compose healthcheck). No auth, no DB.
**Returns** `{"status": "ok"}`.

### `POST /v1/sessions` — login
**Receives** `{ "email": "...", "password": "..." }`.
**Returns** `201` with the user (`id`, `company_id`, `first_name`, `last_name`,
`email`, `job_title`, `visibility` — never credential material) and sets the
cookie `arol_session` (`HttpOnly`, `SameSite=Lax`, `Secure` when
`SESSION_COOKIE_SECURE=true`, no `Max-Age`: expiry is enforced server-side).
`401 "Invalid email or password"` for every kind of failure.

### `GET /v1/sessions/current` — who am I
**Returns** the same user object, or `401`. The frontend calls it on load to
know whether it is logged in.

### `DELETE /v1/sessions/current` — logout
Deletes the session and the cookie. **Returns** `204`. Idempotent.

### `POST /v1/chat`
Non-streaming chat: runs the graph to completion and returns one JSON object.

**Receives** — `ChatRequest`:

| Field        | Type  | Description |
|--------------|-------|-------------|
| `query`      | `str` | The user's question, 1-2000 characters after stripping whitespace. |
| `machine_id` | `str` | The machine the conversation is about. Must belong to the user's company. |
| `thread_id`  | `UUID \| null` | Omit on the first turn; send back the returned id to continue. The thread must belong to the user and to the same `machine_id`. |

**Returns** — `ChatResponse`: `answer` (str), `sources` (list of objects with
a `kind` discriminator, only from this turn, deduplicated), `denied` (list of
`{ tool, domain, message }`, the tool calls refused by the access model in
this turn), `thread_id` (UUID).

```json
{
  "answer": "...",
  "sources": [{ "kind": "manual", "doc": "15610_manual_EN.pdf", "page": 89, "snippet": "..." }],
  "thread_id": "57862673-7b99-401e-be0c-3942c1a3110f"
}
```

**Errors**: `401` not logged in; `403` guest account (the assistant is closed
to guests, also on the stream and history endpoints); `404` machine not in the
user's company, or
thread not owned by the user / opened on another machine; `422` invalid body.

> **Cross-service contract**: a manual source's `doc` must equal
> `manuals.filename` (`<serialNumber>_manual_<LANG>.pdf`), or the frontend
> cannot resolve a citation back to a manual row.

### `POST /v1/chat/stream`
Streaming chat over **Server-Sent Events**. Same request body and same
pre-stream errors (`401`/`404`/`422`) as `POST /v1/chat`; once the stream has
started the status is `200` and failures arrive as events. Each event is a
frame `event: <type>\ndata: <json>\n\n`.

| Event      | When | `data` payload |
|------------|------|----------------|
| `start`    | Once, first | `{ "type": "start", "thread_id": "<uuid>", "is_new": true\|false }` |
| `thinking` | While the model reasons | `{ "type": "thinking", "text": "<chunk>" }` — show collapsed/greyed |
| `status`   | When the model calls a tool | `{ "type": "status", "tool": "search_manuals", "message": "Consulting search_manuals..." }` |
| `token`    | While the answer is generated | `{ "type": "token", "text": "<chunk>" }` — concatenate to rebuild the answer |
| `reset`    | A failed generation is being recovered | `{ "type": "reset" }` — clear accumulated answer and thinking text before consuming replacement tokens |
| `denied`   | When a tool call is refused by the access model | `{ "type": "denied", "tool": "search_iot", "domain": "operational", "message": "..." }` — emitted by code, show as a distinct notice |
| `error`    | Agent failure (recoverable) or graph failure (fatal) | `{ "type": "error", "recoverable": true\|false, "message": "..." }` — fatal errors carry a generic message; details go to the log |
| `sources`  | Once, after the graph ends | `{ "type": "sources", "sources": [ ... ] }` |
| `done`     | Once, last | `{ "type": "done", "thread_id": "<uuid>" }` |

**Frontend note**: `EventSource` only supports `GET`; read this `POST` stream
with `fetch` + `ReadableStream` and parse the frames manually, with
`credentials: "include"`.

### `GET /v1/conversations?machine_id=MCH-0001`
The caller's own conversations, **newest first**; `machine_id` is optional
and narrows the list to one machine. The user comes from the session cookie,
never from the request.

**Returns** a list of `{ "thread_id": "<uuid>", "preview": "<start of the
first question>", "created_at": "<UTC datetime>" }`. A `machine_id` that is
not the caller's simply yields `[]`. `401` without a session, `403` for
guest accounts.

### `GET /v1/conversations/{thread_id}/messages`
Re-reads a past conversation for re-display.

**Returns** — `ConversationHistory`: `thread_id`, `machine_id` (the machine the
thread is pinned to) and `messages`, each with `role` (`user`/`assistant`),
`content`, `sources` and `denied` (both always present, empty for user
messages).
`404` if the thread does not exist or is not the caller's; `422` if the id is
not a UUID. A thread whose first turn failed exists with an empty message list.

### `GET /v1/machines`
The caller's fleet: machines of their own company only, ordered by id.
**Returns** a list of `MachineOut`: `id`, `company_id`, `model_id`,
`serial_number`, `delivery_date` (`YYYY-MM-DD`), `plant_location`,
`configuration_profile`, `plc_family`, `software_version` (nullable).

### `GET /v1/machines/by-serial/{serial_number}`
Machine by the serial printed on it (QR code, manual filename, citation).
**Returns** one `MachineOut`, or `404`. Declared before
`/machines/{machine_id}/manual`, which has the same shape: FastAPI matches
routes in declaration order.

### `GET /v1/machines/{machine_id}`
Machine detail — the landing target of the QR-scan use case. `404` if missing
or not in the caller's company.

### `GET /v1/machines/{machine_id}/manual`
The manual of a machine — singular, one object. Two distinct `404`s:
*machine not found* and *no manual registered for this machine*.

### `GET /v1/manuals/{manual_id}`
**Returns** one `ManualOut`: `id`, `machine_id`, `title`, `filename`,
`language`, `content_type`, `size`, `uploaded_at` (UTC, with offset) and
`url` — the relative path of the file endpoint, to be followed, not built.

### `GET /v1/manuals/{manual_id}/file`
The PDF, with `Content-Disposition: inline` (displayed by the browser; the
original filename is kept for "save as"). The cookie travels automatically,
so a plain link or an `<iframe>` works. `404` if the manual is missing or not
in the caller's company; `500` (logged with the path) if the row exists but
the file is missing on disk — the DB and the disk disagree, which is a server
fault.

## Requirements

- Python 3.12, dependencies in `requirements.txt` (`fastapi`, `sqlmodel`,
  `aiosqlite`, `langgraph`, `langgraph-checkpoint-sqlite`, `langchain`,
  `langchain-ollama`, `langfuse`, `httpx`, `tenacity`, `pydantic-settings`)
  and the shared `contracts` package
- Ollama with a tool-calling model (`gpt-oss:20b`, also used by the agents)
- The agents service and the mock-backoffice running
- A reachable Langfuse instance, credentials in `.env`
- The manual PDFs in `data/manuals/` at the **monorepo root**

## Running with Docker Compose (recommended)

From the monorepo root:

```bash
docker compose up -d --build
docker compose logs -f backend
```

The startup log must show `Seeded 5 companies, 19 users, 6 models, 8
machines`, `19 user(s) provisioned`, and one `Manual … linked to machine …`
line per PDF. The first time, also build the agents' search index
(`agents/README.md`, step 9) and then **restart the agents container**: its
Chroma client is opened once and does not see an index written by another
process.

## Local setup (without Docker)

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate          # Linux
# .\venv\Scripts\Activate.ps1     # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env              # set ORCHESTRATOR_OLLAMA_MODEL and the LANGFUSE_* keys
uvicorn app.main:app --reload --port 8000
```

With the defaults, `MANUALS_DIR` points to `../data/manuals` and the DBs are
created in `backend/data/`. The agents service (port 8001), the
mock-backoffice (8003) and Langfuse (`../langfuse-local/README`) must be
running.

## Trying the API with curl

`curl` does not keep cookies by itself: `-c` saves them to a file, `-b` sends
them back.

```bash
# login (password shared by every seeded user)
curl -s -c elena.txt -X POST localhost:8000/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{"email":"elena.fabbri@valgrande.example","password":"Arol2026!"}'

curl -s -b elena.txt localhost:8000/v1/machines     # MCH-0001..0003 only

# first turn: capture the thread id
T=$(curl -s -b elena.txt -X POST localhost:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"ciao","machine_id":"MCH-0001"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['thread_id'])")

# streaming turn on the same thread (-N disables curl's buffering)
curl -N -b elena.txt -X POST localhost:8000/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d "{\"query\":\"come regolo la coppia di serraggio?\",\"machine_id\":\"MCH-0001\",\"thread_id\":\"$T\"}"

curl -s -b elena.txt localhost:8000/v1/conversations/$T/messages
curl -s -b elena.txt -X DELETE localhost:8000/v1/sessions/current
```

Swagger UI (`http://localhost:8000/docs`) works too: log in with
`POST /v1/sessions` and the browser keeps the cookie for the following calls.
It buffers streams, so use `curl -N` for `/v1/chat/stream`.

### Inspecting the domain DB

The container has no `sqlite3` CLI; use Python. The `LEFT JOIN` makes a
missing manual visible instead of hiding the row.

```bash
docker compose exec -T backend python - <<'EOF'
import sqlite3
from app.config import settings
con = sqlite3.connect(settings.DOMAIN_DB_PATH)
for t in ("companies","users","machine_models","machines","manuals","sessions","conversations"):
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

## Environment variables

| Variable                       | Description                                              | Local default / Docker value |
|--------------------------------|----------------------------------------------------------|------------------------------|
| `AGENTS_SERVICE_URL`           | Base URL of the agents service (all three agents)        | `http://localhost:8001` / `http://agents:8001` |
| `ORCHESTRATOR_LLM_PROVIDER`    | Only `ollama` is implemented                             | `ollama` |
| `ORCHESTRATOR_OLLAMA_BASE_URL` | Ollama server used by the orchestrator                   | `http://localhost:11434` / `http://host.docker.internal:11434` |
| `ORCHESTRATOR_OLLAMA_MODEL`    | Tool-calling model — **required**                        | `gpt-oss:20b` |
| `ORCHESTRATOR_NUM_CTX`         | Context window, fixed explicitly                         | `4096` |
| `ORCHESTRATOR_MAX_ITERATIONS`  | Max agent->tools round trips per turn                    | `5` |
| `LANGFUSE_PUBLIC_KEY`          | Langfuse public key — **required**                       | `pk-lf-...` |
| `LANGFUSE_SECRET_KEY`          | Langfuse secret key — **required**                       | `sk-lf-...` |
| `LANGFUSE_HOST`                | Langfuse instance                                        | `http://localhost:3000` / `http://langfuse-web:3000` |

| `GUEST_QR_BASE_URL`            | Frontend route encoded in the QR codes                   | `http://localhost:8080/m` |

| `LANGFUSE_TRACING_ENABLED`     | Enable tracing; set `false` to disable it locally         | `true` |

| `SESSION_COOKIE_SECURE`        | Mark the session cookie `Secure` (HTTPS only)            | `false` (set `true` behind HTTPS) |
| `CHECKPOINT_DB_PATH`           | SQLite file with conversation checkpoints                | `backend/data/checkpoints.sqlite` |
| `DOMAIN_DB_PATH`               | SQLite file with the domain DB                           | `backend/data/domain.sqlite` |
| `MANUALS_DIR`                  | Directory scanned for manual PDFs at startup             | `<repo>/data/manuals` / `/data/manuals` |

## Docker notes

- **`./backend` is bind-mounted on `/app`**, so code changes are live on disk,
  but `uvicorn` runs without `--reload`: after editing, run
  `docker compose restart backend`. Rebuild (`--build`) only when
  `requirements.txt` or the Dockerfile change.
- **`restart` does not re-read `environment:`**; after changing the compose
  file use `docker compose up -d --force-recreate backend`.
- **Only the backend should be reachable from outside.** The compose file
  publishes the agents (`8001`) and the mock-backoffice (`8003`) ports, which
  is convenient for testing them with curl but lets anyone reaching the host
  call them directly, bypassing both the tenant and the visibility checks.
  For a demo, remove their `ports:` sections: the backend still reaches them
  by service name on the compose network.
- **Both SQLite files live in `backend/data/`** (persisted by the bind mount).
  With WAL, the `-wal` and `-shm` side files are normal; do not delete them
  while the backend runs.
- **`create_all` does not migrate.** It creates missing tables and never
  alters existing ones: after a schema change delete `domain.sqlite`. Delete
  `checkpoints.sqlite` too if the old conversations should go, since threads
  without a `conversations` row answer `404`.
- **`data/manuals` at the root**: if Docker created it before you did (a bind
  mount source that does not exist is created by the daemon), it belongs to
  `root`; fix it with `sudo chown -R "$USER":"$USER" data`.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `Manual ingest complete: 0 new manual(s)` with no warning | `MANUALS_DIR` exists but is empty: the PDFs are not in `<repo>/data/manuals` |
| `Manuals directory … not found` | `MANUALS_DIR` wrong or the volume not mounted |
| Chat event `error`: *Could not reach Manuals agent* | `AGENTS_SERVICE_URL` wrong, or the agents container not healthy |
| Manuals answers say "not found", `sources` empty | The agents' Chroma index was never built (agents README, step 9) |
| Agents `500`, `chromadb … Error finding id` | Ingestion ran while the agents server was up: `docker compose restart agents` |
| `401` right after logging in with curl | Missing `-b <file>`, or a different cookie file than the one used at login |
| `422` on `thread_id` | Not a full UUID (5 groups) — often a truncated copy-paste or an unescaped `$` in the shell |

## Known limitations / next steps

- **Grounding is prompt-based.** Rules in the system prompt reduce invented
  content but a 20B model can still add unsupported details; the most
  effective lever is a faithful `answer` from the agents, plus an automated
  evaluation of answers against their sources, which does not exist yet.
- **`sources` is untyped** (`list[dict]`): a discriminated union on `kind`
  would document every variant in OpenAPI and validate it server-side.
- **No schema migrations** (Alembic): schema changes require deleting the DB.
- **Manuals are a shared folder**: the target design (agents README, last
  section) is upload through the backend, which then asks the agents to index
  the file over HTTP.
- **`MachineOut` exposes `model_id`, not a readable model name**; a join or a
  models endpoint is needed.
- **Checkpointing is single-node** (a local SQLite file); a multi-instance
  deployment would use `AsyncPostgresSaver`.
- **No rate limiting on login** and no CSRF token beyond `SameSite=Lax`.
- **The manual file URL is relative** (`/v1/...`): behind the frontend's
  nginx it works only if `/v1` is proxied to the backend.
