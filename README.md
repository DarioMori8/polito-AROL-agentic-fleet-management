# Polito x AROL - Agentic Fleet Management

Conversational platform for AROL plant operators: an LLM orchestrator routes each question to specialized agents for technical manuals, commercial data, telemetry, alarms and maintenance.

## Consegna al docente: avvio automatico

La guida per installare e provare il progetto è **[CONSEGNA.md](CONSEGNA.md)**.
Il pacchetto di consegna usa `compose.delivery.yml`: include Ollama, scarica
Llama 3.1 8B e il modello di embedding, indicizza i manuali e inizializza Langfuse.
È sufficiente installare e aprire Docker, estrarre il pacchetto e avviare
`avvia.bat` su Windows oppure `sh avvia.sh` su macOS/Linux. Non serve creare `.env`.

Le sezioni seguenti descrivono invece l'ambiente di **sviluppo** preesistente,
con Ollama sull'host e il file `docker-compose.yml`.

## Repository structure

| Folder | Content | Port | Docs |
|---|---|---|---|
| `frontend/` | React PWA: login, QR scanning, chat, manual viewer | 8080 | [frontend/README.md](frontend/README.md) |
| `backend/` | FastAPI API, authentication, LangGraph orchestrator, machine registry | 8000 | [backend/README.md](backend/README.md) |
| `agents/` | Manuals Agent (RAG on Chroma), Docs Agent, IoT Agent | 8001 | [agents/README.md](agents/README.md) |
| `mock-backoffice/` | Stands in for the ERP/CRM: serves the Q2 dataset (orders, quotes, telemetry, alarms) | 8003 | [mock-backoffice/README.md](mock-backoffice/README.md) |
| `langfuse-local/` | Self-hosted Langfuse instance for tracing | 3000 | [langfuse-local/README.md](langfuse-local/README.md) |
| `shared/contracts/` | Pydantic schemas shared by backend and agents | — | — |
| `data/manuals/` | Manual PDFs (not versioned) | — | — |

Everything starts from a single `docker-compose.yml` at the root, which also includes the Langfuse one. The only component outside Docker is **Ollama**, which runs directly on the host machine.

The configuration files are also one per repository, all at the root: `.env` (from `.env.example`), `.gitignore` and `.dockerignore`. Every image is built with the repo root as context and its own `<service>/Dockerfile`, so the single `.dockerignore` applies to all of them.

## Machine setup

### 1. Requirements

- Docker and Docker Compose (`docker compose version` must respond)
- Ollama ([ollama.com/download](https://ollama.com/download))
- A GPU with at least 12 GB of VRAM is recommended. It also works without a GPU, but much more slowly.

### 2. Ollama

Download the two models, one for chat and one for embeddings:

```bash
ollama pull gpt-oss:20b
```

```bash
ollama pull nomic-embed-text
```

**Linux only:** by default Ollama listens only on `127.0.0.1`, so the containers cannot reach it. Make it listen on all interfaces:

```bash
sudo systemctl edit ollama
```

In the editor, add these lines and save:

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

Then restart the service:

```bash
sudo systemctl restart ollama
```

This is not needed on macOS and Windows: Docker Desktop already reaches the host.

Check that Ollama responds and lists both models:

```bash
curl http://localhost:11434/api/tags
```

### 3. `.env` file

The project uses a single `.env` at the root. Create it from the template:

```bash
cp .env.example .env
```

Then replace the `<...>` values of the Langfuse instance. Generate the three secrets with:

```bash
openssl rand -base64 32   # NEXTAUTH_SECRET
openssl rand -base64 16   # SALT
openssl rand -hex 32      # ENCRYPTION_KEY
```

The other rules on these values are in [langfuse-local/README.md](langfuse-local/README.md). Leave `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` as they are for now: you get them from Langfuse in step 5.

### 4. Manuals

The manuals are AROL property and are not in the repository. Download them from the course dataset package and copy them into `data/manuals/`:

```
data/manuals/
├── 15610_manual_EN.pdf
├── 17203_manual_EN.pdf
├── ...
└── A4344_manual_EN.pdf
```

Keep the file names as `<serialNumber>_manual_<LANG>.pdf`: the serial is what links a manual to its machine.

### 5. Langfuse API keys

Start Langfuse alone (the first time it pulls postgres, clickhouse, redis and minio, so it is slow):

```bash
docker compose -f langfuse-local/docker-compose.yml --env-file .env up -d
```

Then open [localhost:3000](http://localhost:3000):

1. sign up (the account is local);
2. create an organization and a project inside it;
3. in the project, go to **Settings → API Keys** and create a key pair;
4. copy the `pk-lf-...` and `sk-lf-...` keys into `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `.env`.

### 6. Start

```bash
docker compose up -d --build
```

The healthchecks start the services in order: mock-backoffice, agents, backend, frontend.

### 7. Index the manuals (first time only)

The Manuals Agent searches a Chroma index, which must be built once with the stack running:

```bash
docker compose stop frontend backend agents
docker compose run --rm --no-deps agents python -m manuals_agent.ingestion
```

It takes several minutes. The index is saved in `agents/data/chroma/` and survives `docker compose down`. When it finishes, start the application again so the agents see the new index:

```bash
docker compose up -d agents backend frontend
```

### 8. Check

```bash
docker compose ps
```

All services must be `healthy` or `running`. Then:

- **App:** [localhost:8080](http://localhost:8080). For example, log in as `elena.fabbri@valgrande.example` with password `Arol2026!`, the same for every dev user.
- **Langfuse:** [localhost:3000](http://localhost:3000), with the account created in step 5.
- **Backend API:** [localhost:8000/docs](http://localhost:8000/docs).

The healthchecks do not check Ollama: if the containers are `healthy` but every chat question fails, go back to step 2.

## Tests

All Python tests use `unittest`. Each service's tests run inside its container:

```bash
docker compose exec backend python -m unittest discover -s tests
```

```bash
docker compose exec agents python -m unittest discover -s tests
```

```bash
docker compose exec mock-backoffice python -m unittest discover -s tests
```

The frontend tests are Storybook stories run by Vitest in a real Chromium browser. The frontend image only contains Nginx, so they run in the official Playwright image (same version as in `package-lock.json`). The code is mounted read-only and copied inside the container, so nothing is written to your folder:

```bash
docker run --rm -v "$PWD/frontend":/src:ro mcr.microsoft.com/playwright:v1.61.1-noble sh -c "mkdir /app && cd /src && tar --exclude=node_modules -cf - . | tar -C /app -xf - && cd /app && npm ci && npm test"
```

`tests/` at the root contains the integration test of the tracing between backend and agents (real Langfuse SDK, LangGraph and ASGI endpoints; only Ollama and the backoffice are simulated). It needs the dependencies of both services in one environment:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
```

```bash
(cd backend && pip install -r requirements.txt) && (cd agents && pip install -r requirements.txt)
```

```bash
PYTHONPATH=backend:agents python -m unittest discover -s tests
```

## Dependencies

Each Python service lists in `requirements.txt` only the libraries it uses directly, pinned to an exact version (`==`). Libraries used by more than one service (FastAPI, Pydantic, httpx, Langfuse, …) have the same version everywhere. After changing a `requirements.txt`, rebuild the image (`docker compose up -d --build <service>`).

## Useful commands

| What | Command |
|---|---|
| Logs of a service | `docker compose logs -f backend` |
| Restart after a code change | `docker compose restart backend` |
| Rebuild after a dependency or Dockerfile change | `docker compose up -d --build backend` |
| Apply a `.env` change | `docker compose up -d --force-recreate` |
| Stop everything | `docker compose down` |

To work on a single service outside Docker, follow the README in its folder.
