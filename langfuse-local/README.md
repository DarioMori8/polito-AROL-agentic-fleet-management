# Langfuse (self-hosted)

Local Langfuse instance used to trace the orchestrator and the agents. It is infrastructure, not application code: `langfuse-local/docker-compose.yml` is included by the root `docker-compose.yml`, so it starts with the rest of the stack.

All its variables are in the project's single `.env` at the repo root, in the *Langfuse self-hosted instance* section of [`.env.example`](../.env.example).

## Prerequisites

- Docker and Docker Compose
- Port `3000` free (UI and API)

## 1. Fill in the `.env`

From the repo root, if you haven't done it yet:

```bash
cp .env.example .env
```

Generate the three secrets and paste them into `NEXTAUTH_SECRET`, `SALT` and `ENCRYPTION_KEY`:

```bash
openssl rand -base64 32   # NEXTAUTH_SECRET
openssl rand -base64 16   # SALT
openssl rand -hex 32      # ENCRYPTION_KEY
```

Then replace the other `<...>` values of the section. Keep these in sync:

- `DATABASE_URL` must contain the same password as `POSTGRES_PASSWORD`.
- The `LANGFUSE_S3_*_SECRET_ACCESS_KEY` values must be equal to `MINIO_ROOT_PASSWORD` (and the `*_ACCESS_KEY_ID` values to `MINIO_ROOT_USER`).

## 2. Start it

With the whole stack, from the repo root:

```bash
docker compose up -d
```

Only Langfuse:

```bash
docker compose -f langfuse-local/docker-compose.yml --env-file .env up -d
```

The first time, start Langfuse alone: you need it running to create the API keys used by backend and agents.

## 3. Create the API keys

1. Open `http://localhost:3000` and sign up (the account is local).
2. Create an organization and a project inside it.
3. In the project, go to **Settings → API Keys** and create a key pair.
4. Copy the `pk-lf-...` and `sk-lf-...` keys into `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in the root `.env`.
5. Start (or recreate) backend and agents so they read the new keys:

```bash
docker compose up -d --force-recreate backend agents
```

## 4. Check that traces arrive

Log in to the app, open a machine and ask a question. A new trace should appear in Langfuse within a few seconds (ingestion is asynchronous). Each chat turn is one trace, containing the orchestrator and the agent calls; see `agents/README.md` for the detail of what is traced.

If nothing shows up:

- the `LANGFUSE_*` keys in `.env` are not the project's keys;
- backend and agents were not recreated after changing `.env` (`restart` is not enough);
- `docker compose ps` does not show all Langfuse services as `healthy`.

## Services

| Service | Role |
|---|---|
| `langfuse-web` | UI and API, receives the traces |
| `langfuse-worker` | Reads the queue and writes the traces to ClickHouse |
| `postgres` | Users, projects, API keys |
| `clickhouse` | The traces |
| `redis` | Queue between web and worker, cache |
| `minio` | S3-compatible storage for events and attachments |

A trace goes `langfuse-web` → `redis` → `langfuse-worker` → `clickhouse`. Since the write is asynchronous, tracing does not slow down the chat responses.
