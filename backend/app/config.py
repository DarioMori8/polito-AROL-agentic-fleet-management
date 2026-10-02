import os
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


# Anchors computed from this file's location, never from the current working
# directory: the result is the same whether uvicorn is launched from the
# backend folder, from the repo root, or inside the container.
#
#   <backend>/app/config.py  ->  BACKEND_ROOT = <backend>
#
# In the container the backend is mounted at /app, so BACKEND_ROOT is /app and
# DATA_DIR is /app/data, i.e. ./backend/data on the host (persisted by the
# bind mount).
BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_ROOT / "data"


class Settings(BaseSettings):
    """
    Single typed source of configuration for the backend.

    Resolution order for every field: process environment (docker-compose
    `environment:`) > backend/.env > the default below. Fields without a
    default are mandatory: if they are missing, instantiating Settings raises
    at import time and the app refuses to start (fail fast).

    Defaults target LOCAL development (everything on localhost). Inside Docker
    every network address must be overridden by docker-compose, because there
    `localhost` is the container itself.
    """

    # Anchored to BACKEND_ROOT rather than the CWD, like every other path here.
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        extra="ignore",
    )

    # --- Downstream agents service
    # Docker: http://agents:8001 (service name on the compose network).
    AGENTS_SERVICE_URL: str = "http://localhost:8001"

    # --- Orchestrator LLM
    # Only Ollama is implemented. Declared as a Literal so that a different
    # value fails validation instead of being silently ignored.
    ORCHESTRATOR_LLM_PROVIDER: Literal["ollama"] = "ollama"
    # Docker: http://host.docker.internal:11434 (Ollama runs on the host).
    ORCHESTRATOR_OLLAMA_BASE_URL: str = "http://localhost:11434"
    ORCHESTRATOR_OLLAMA_MODEL: str
    # Max agent->tools round trips per turn; the graph's recursion_limit is
    # derived from it.
    ORCHESTRATOR_MAX_ITERATIONS: int = 5
    ORCHESTRATOR_NUM_CTX: int = 4096

    # --- Observability (Langfuse)
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_SECRET_KEY: str
    # Docker: http://langfuse-web:3000 (service name via compose `include`).
    LANGFUSE_HOST: str = "http://localhost:3000"

    # --- Authentication
    # The session cookie is marked Secure only when this is True. Secure
    # cookies are sent over HTTPS only, so it must stay False for local HTTP
    # development and be turned on behind HTTPS.
    SESSION_COOKIE_SECURE: bool = False

    # --- Storage
    # The two SQLite paths stay plain strings because their consumers
    # (the aiosqlite URL and AsyncSqliteSaver.from_conn_string) expect a str.
    # SQLite does not create missing parent directories: DATA_DIR must exist.
    CHECKPOINT_DB_PATH: str = str(DATA_DIR / "checkpoints.sqlite")
    DOMAIN_DB_PATH: str = str(DATA_DIR / "domain.sqlite")
    # Shared with the agents service. Locally it defaults to the repo-level
    # ./data/manuals; in Docker it must be set to /data/manuals, where the
    # shared volume is mounted.
    MANUALS_DIR: Path = BACKEND_ROOT.parent / "data" / "manuals"

    # --- Guest QR codes
    # Base URL embedded in per-machine QR codes for plant-floor visitors.
    # The QR encodes <GUEST_QR_BASE_URL>/<machine_id>?u=<email>&k=<password>.
    # Must match the frontend route: /machine/:id (see App.jsx).
    # In production set this to the public frontend URL (e.g. https://arol.example.com/machine).
    # In Docker the frontend is exposed on port 8080 of the host.
    GUEST_QR_BASE_URL: str = "http://localhost:8080/machine"


settings = Settings()


# Explicit bridge to os.environ. Langfuse's CallbackHandler() reads its
# credentials straight from the process environment, not from this Settings
# object, and pydantic-settings reads backend/.env into the model WITHOUT
# exporting it to os.environ. Without this block, settings.LANGFUSE_PUBLIC_KEY
# would hold the right value while CallbackHandler() still saw nothing.
#
# setdefault never overwrites: a variable already provided by the real
# environment (docker-compose) always wins. In Docker this block is therefore
# a no-op; it matters only for local runs driven by the .env file.
#
# It works only because this module is imported BEFORE CallbackHandler() is
# instantiated (orchestrator.py imports settings first).
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)
os.environ.setdefault("LANGFUSE_HOST", settings.LANGFUSE_HOST)
