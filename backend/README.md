# Backend

FastAPI service that exposes the API used by the frontend. It handles:

- **authentication** with server-side sessions (`HttpOnly` cookie);
- **chat**: a LangGraph orchestrator decides which agent to call (Manuals, Docs, IoT) and returns the answer, optionally streamed over SSE;
- **read-only resources**: machines and PDF manuals of the user's company;
- **domain database** (SQLite): companies, users, models, machines, manuals, sessions and conversation ownership.

Telemetry, alarms, maintenance, orders and quotes are **not** stored here: they belong to the `mock-backoffice`, and the backend reaches them only through the agents.

## Architecture

```
Frontend (session cookie)
  └─ Backend :8000
       ├─ /v1/sessions              login / current user / logout
       ├─ /v1/machines, /v1/manuals resources scoped to the user's company
       └─ /v1/chat, /v1/chat/stream → LangGraphOrchestrator
            1. prepare_turn: machine in the user's company? thread owned by the user?
            2. agent node (ChatOllama + tools) ──tool_calls──▶ tools node
                 ├─ search_manuals → Manuals Agent (RAG on Chroma)
                 ├─ search_docs    → Docs Agent    (quotes, orders)
                 └─ search_iot     → IoT Agent     (telemetry, alarms, tickets)
               ◀── back to the agent node until the answer is plain text
```

The loop is a LangGraph `StateGraph` with `ToolNode` and `tools_condition`. On top of it:

- **Persistent checkpoints** with `AsyncSqliteSaver`: turns with the same `thread_id` form one conversation, which survives restarts.
- **Langfuse tracing**: one trace per turn, grouped by user and conversation. The W3C context (`traceparent`, `baggage`) is propagated to the agents, so their operations end up in the same trace.
- **Ollama parser recovery**: if Ollama rejects a tool call after the turn has already collected tool results, the model regenerates the answer once without tools. When streaming, the client first receives a `reset` event.

## Structure

```
backend/
├── app/
│   ├── main.py             # FastAPI app, lifespan (tables, seed, graph), CORS, routers
│   ├── config.py           # Settings (pydantic-settings)
│   ├── observability.py    # Langfuse callback and trace propagation to the agents
│   ├── api/
│   │   ├── deps.py         # get_current_user: session cookie check
│   │   └── v1/
│   │       ├── auth.py     # /v1/sessions
│   │       └── chat.py     # /v1/chat, /v1/chat/stream, /v1/conversations
│   ├── orchestrator/
│   │   ├── base.py         # Orchestrator interface, TurnContext, domain errors
│   │   ├── agent_registry.py  # one @tool per agent
│   │   └── orchestrator.py # graph, streaming, history
│   ├── clients/            # HTTP clients for the agents (retry, validation)
│   ├── security/
│   │   ├── access.py       # visibility → allowed data domains
│   │   ├── passwords.py    # scrypt hashing
│   │   └── session.py      # session creation / lookup / logout
│   ├── db/
│   │   ├── engine.py       # async engine, SQLite PRAGMAs
│   │   ├── models.py       # SQLModel tables
│   │   ├── seed.py         # dataset fixtures, dev credentials, manual registration
│   │   └── guest_accounts.py  # guest passwords and QR URLs (also a CLI)
│   ├── models/             # backend request/response schemas
│   └── resources/          # company-scoped repositories + machine/manual endpoints
├── data/                   # created at startup, not versioned
│   ├── domain.sqlite       # domain database
│   ├── checkpoints.sqlite  # LangGraph conversations
│   └── qr_urls.txt         # QR URLs with the guest passwords in clear text
├── tests/                  # unittest suite
├── requirements.txt
└── Dockerfile
```

The manual PDFs are not in `backend/` but in `data/manuals/` at the repo root, shared with the `agents` service.

## Access control

Every request goes through two checks, both enforced in code and never left to the LLM.

**1. Company (`company_id`).** Every query and every agent call is limited to the user's company. A resource of another company answers `404`, the same as a missing one.

**2. Visibility (`visibility`).** Decides which kinds of data the user can see inside their own company. The rule is defined only in `app/security/access.py`:

| visibility   | Machines and manuals (`search_manuals`) | Operational (`search_iot`) | Commercial (`search_docs`) |
|--------------|:---:|:---:|:---:|
| `full`       | yes | yes | yes |
| `technician` | yes | yes | no |
| `commercial` | yes | no | yes |
| `guest`      | yes (no chat) | no | no |

In practice:

- `machine_id`, `company_id` and `visibility` are passed to the tools by the server through `RunnableConfig`. The LLM only controls the query, so it cannot widen the scope.
- If a tool is not allowed, the agent is never called: the tool returns an explicit denial and the stream emits a `denied` event.
- A missing or unknown visibility grants nothing.
- The check only holds if the agents and the mock-backoffice are reachable from the backend alone (see [Notes](#notes)).

### Guest access via QR

Someone who scans a machine's QR code without an account is logged in as their company's guest and can only see manuals.

- One guest account per company (`guest@<company domain>`), created by the seed, each with its own random password.
- The QR contains the credentials: `<GUEST_QR_BASE_URL>/<machine_id>?u=<email>&k=<password>`. The frontend uses them for a normal `POST /v1/sessions`.
- Only the hash is stored in the DB. The clear-text passwords are written once to `data/qr_urls.txt` (mode `0600`, do not commit it).
- Chat, stream and history answer `403` to guests.
- The "only the scanned machine's manual" limit is enforced by the frontend; the backend lets a guest read every manual of their company.

To change a company's guest password (for example if a QR code has leaked) and regenerate its QR URLs:

```bash
docker compose exec backend python -m app.db.guest_accounts rotate CMP-001
```

## Domain database

SQLite (`DOMAIN_DB_PATH`), based on the `AROL_Q2_synthetic_fleet_dataset.xlsx` dataset. It is a separate file from the checkpoint DB.

| Table            | Content |
|------------------|---------|
| `companies`      | Customer companies (`CMP-001`…). |
| `users`          | Users (`USR-001`…, guests `USR-G001`…), with `company_id`, unique `email`, `visibility`, password hash and salt. |
| `machine_models` | Machine models (`MDL-100`…). |
| `machines`       | Machines (`MCH-0001`…), with company, model, unique `serial_number`, PLC, software version. |
| `manuals`        | One manual per machine (UUID id, unique `filename`, path on disk). |
| `sessions`       | Login sessions: stores the SHA-256 of the token, not the token. |
| `conversations`  | Owner and machine of each `thread_id`, plus a preview of the first question. The messages live in the checkpoint DB. |

Main choices:

- The dataset ids (`CMP-…`, `USR-…`, `MCH-…`) are the primary keys, because they are shared with the mock-backoffice and the agents.
- `serial_number` is the key used from outside (manual filename, QR code) to find the machine.
- SQLite `foreign_keys` are turned on explicitly, together with WAL and `busy_timeout`.
- There are no migrations: `create_all` only creates missing tables.

### Seed at startup

`seed.py` runs at every startup and is idempotent:

1. loads the dataset if the DB is empty;
2. creates the guest accounts and their passwords;
3. gives the dev password `Arol2026!` to users that have none;
4. registers the manuals found in `MANUALS_DIR` named `<serialNumber>_manual_<LANG>.pdf`, linking them to the machine through the serial.

The seed registers the PDFs for download only. The search index (Chroma) is built by the `agents` service with its own ingestion.

## API

All endpoints except `/health` and `POST /v1/sessions` require the session cookie (`arol_session`); without it they answer `401`. Interactive docs are at `http://localhost:8000/docs`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Healthcheck, no authentication. |
| `POST` | `/v1/sessions` | Login with `{email, password}`. Answers `201` with the user and sets the cookie. |
| `GET` | `/v1/sessions/current` | Logged-in user, or `401`. |
| `DELETE` | `/v1/sessions/current` | Logout, `204`. |
| `POST` | `/v1/chat` | Chat without streaming. |
| `POST` | `/v1/chat/stream` | Chat streamed over SSE. |
| `GET` | `/v1/conversations?machine_id=…` | The user's conversations, newest first. `machine_id` is optional. |
| `GET` | `/v1/conversations/{thread_id}/messages` | Messages of a conversation, with sources and denials for each answer. |
| `GET` | `/v1/machines` | Machines of the user's company. |
| `GET` | `/v1/machines/by-serial/{serial}` | Machine by serial number. |
| `GET` | `/v1/machines/{machine_id}` | Machine details. |
| `GET` | `/v1/machines/{machine_id}/manual` | Metadata of the machine's manual. |
| `GET` | `/v1/manuals/{manual_id}` | Manual metadata, with the file `url`. |
| `GET` | `/v1/manuals/{manual_id}/file` | The PDF (`inline`). Works directly in a link or an `<iframe>`. |

PDFs are served only through `/v1/manuals/{id}/file`: there is no static folder, so both login and company scoping apply.

### Chat

Body of `/v1/chat` and `/v1/chat/stream`:

| Field | Type | Notes |
|---|---|---|
| `query` | `str` | 1-2000 characters. |
| `machine_id` | `str` | Must belong to the user's company. |
| `thread_id` | `UUID \| null` | Empty on the first turn, then send back the one received. Must belong to the user and to the same machine. |

`/v1/chat` returns:

```json
{
  "answer": "...",
  "sources": [{ "kind": "manual", "doc": "15610_manual_EN.pdf", "page": 89, "snippet": "..." }],
  "denied": [],
  "thread_id": "57862673-7b99-401e-be0c-3942c1a3110f"
}
```

`sources` only contains the sources of the current turn, without duplicates. The `kind` field gives the type: `manual`, `document`, `order`, `quote`, `health`, `telemetry`, `alarms`, `maintenance`.

Errors: `401` not logged in, `403` guest, `404` machine or thread not owned by the user, `422` invalid body.

### Stream events

`/v1/chat/stream` answers with frames `event: <type>\ndata: <json>\n\n`. The `401/403/404/422` errors arrive before the stream as normal HTTP statuses; once the stream has started, errors arrive only as `error` events.

| Event | When | Payload |
|---|---|---|
| `start` | first event | `thread_id`, `is_new` |
| `thinking` | model reasoning | `text` |
| `status` | the model calls a tool | `tool`, `message` |
| `token` | answer generation | `text` (to concatenate) |
| `reset` | recovery after a failed generation | the client must clear the accumulated answer and thinking |
| `denied` | tool refused by access control | `tool`, `domain`, `message` |
| `error` | agent or graph failure | `recoverable`, `message` |
| `sources` | end of the graph | `sources` |
| `done` | last event | `thread_id` |

`EventSource` only supports `GET`, so in the browser the stream must be read with `fetch` + `ReadableStream` and `credentials: "include"`.

## Running

### Requirements

- Ollama running with a tool-calling model (`gpt-oss:20b`)
- `agents` and `mock-backoffice` services running
- Langfuse running, with its keys
- Manual PDFs in `data/manuals/` at the repo root

### Docker Compose (recommended)

From the repo root, after creating the root `.env` from `.env.example`:

```bash
docker compose up -d --build
```

```bash
docker compose logs -f backend
```

The startup log should show `Seeded 5 companies, 19 users, 6 models, 8 machines` and one `Manual … linked to machine …` line per PDF.

### Local

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The backend reads the project's single `.env` at the repo root (not `backend/.env`). It needs at least `ORCHESTRATOR_OLLAMA_MODEL`, `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`.

With the defaults the backend expects agents on `:8001`, mock-backoffice on `:8003`, Langfuse on `:3000` and the manuals in `../data/manuals`.

### Trying it with curl

All seeded users have the password `Arol2026!`. `-c` makes curl save the cookie and `-b` sends it back.

```bash
curl -s -c cookie.txt -X POST localhost:8000/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{"email":"elena.fabbri@valgrande.example","password":"Arol2026!"}'
```

```bash
curl -s -b cookie.txt localhost:8000/v1/machines
```

```bash
curl -N -b cookie.txt -X POST localhost:8000/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"query":"how do I adjust the capping torque?","machine_id":"MCH-0001"}'
```

`-N` turns off curl's buffering. Swagger (`/docs`) buffers streams, so use curl for `/v1/chat/stream`.

## Tests

```bash
docker compose exec backend python -m unittest discover -s tests
```

The cross-service tracing test is in `tests/` at the repo root (see the root README).

## Environment variables

Priority: environment variables (compose) > root `.env` > defaults.

| Variable | Description | Local default / Docker |
|---|---|---|
| `AGENTS_SERVICE_URL` | URL of the agents service | `http://localhost:8001` / `http://agents:8001` |
| `AGENTS_REQUEST_TIMEOUT_SECONDS` | Max wait for an agent's answer (connect timeout is 5 s) | `240` |
| `ORCHESTRATOR_LLM_PROVIDER` | LLM provider, only `ollama` | `ollama` |
| `ORCHESTRATOR_OLLAMA_BASE_URL` | Ollama URL | `http://localhost:11434` / `http://host.docker.internal:11434` |
| `ORCHESTRATOR_OLLAMA_MODEL` | Orchestrator model, **required** | — / `gpt-oss:20b` |
| `ORCHESTRATOR_NUM_CTX` | Context window | `4096` / `16384` |
| `ORCHESTRATOR_MAX_ITERATIONS` | Max agent → tools round trips per turn | `5` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key, **required** | — |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key, **required** | — |
| `LANGFUSE_HOST` | Langfuse URL | `http://localhost:3000` / `http://langfuse-web:3000` |
| `LANGFUSE_TRACING_ENABLED` | Enables tracing | `true` |
| `SESSION_COOKIE_SECURE` | `Secure` cookie (HTTPS only) | `false` |
| `GUEST_QR_BASE_URL` | Frontend route used in the QR codes | `http://localhost:8080/machine` |
| `DOMAIN_DB_PATH` | Domain DB file | `backend/data/domain.sqlite` |
| `CHECKPOINT_DB_PATH` | Checkpoint file | `backend/data/checkpoints.sqlite` |
| `MANUALS_DIR` | PDF folder | `<repo>/data/manuals` / `/data/manuals` |

If `ORCHESTRATOR_NUM_CTX` is too large for the available VRAM, Ollama moves part of the model to the CPU and gets much slower. In `ollama ps` the `PROCESSOR` column should read `100% GPU`.

## Notes

- `./backend` is mounted on `/app`, but uvicorn runs without `--reload`: after a change run `docker compose restart backend`. Rebuild only if `requirements.txt` or the `Dockerfile` change.
- `restart` does not re-read the compose `environment:`; in that case use `docker compose up -d --force-recreate backend`.
- After a schema change, delete `data/domain.sqlite` (there are no migrations). Deleting `checkpoints.sqlite` too removes the conversations; threads without a `conversations` row answer `404`.
- The compose file also publishes the agents (`8001`) and mock-backoffice (`8003`) ports. This is handy for testing, but anyone who reaches them bypasses the backend's checks. For a demo, remove those `ports:` sections.
- If Docker created `data/manuals` before you did, the folder belongs to `root`: `sudo chown -R "$USER":"$USER" data`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Manual ingest complete: 0 new manual(s)` | `data/manuals/` is empty |
| `Manuals directory … not found` | Wrong `MANUALS_DIR` or volume not mounted |
| `error` event: *Could not reach Manuals agent* | Wrong `AGENTS_SERVICE_URL` or agents container not healthy |
| "Not found" answers with empty `sources` | Chroma ingestion not done (see `agents/README.md`) |
| `401` right after logging in with curl | Missing `-b cookie.txt` |
| `422` on `thread_id` | Incomplete UUID, often from a truncated copy-paste |

## Known limitations

- Grounding relies only on the prompt: a 20B model can still add details that are not in the sources. There is no automatic evaluation of the answers yet.
- `sources` is untyped (`list[dict]`).
- No schema migrations (Alembic).
- Manuals live in a shared folder; the plan is to upload them through the backend, which then asks the agents to index them.
- `MachineOut` exposes `model_id` but not the model name.
- Checkpoints are in a local SQLite file, so only one backend instance is supported. Multiple instances would need `AsyncPostgresSaver`.
- No rate limiting on login and no CSRF token beyond `SameSite=Lax`.
