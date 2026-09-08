import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    AGENTS_SERVICE_URL: str = "http://localhost:8001"
    # An agent may need several local LLM calls before returning a response.
    AGENTS_REQUEST_TIMEOUT_SECONDS: float = Field(default=240.0, gt=0)


    # nuove, per l'orchestrator
    ORCHESTRATOR_LLM_PROVIDER: str = "ollama"
    ORCHESTRATOR_OLLAMA_BASE_URL: str = "http://localhost:11434"
    ORCHESTRATOR_OLLAMA_MODEL: str
    ORCHESTRATOR_MAX_ITERATIONS: int = 5
    ORCHESTRATOR_NUM_CTX: int = 16384


    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_SECRET_KEY: str
    LANGFUSE_HOST: str = "http://localhost:3000"
    LANGFUSE_BASE_URL: str | None = None


    CHECKPOINT_DB_PATH: str = str(Path(__file__).resolve().parent.parent / "data" / "checkpoints.sqlite")
    DOMAIN_DB_PATH: str = str(Path(__file__).resolve().parent.parent / "data" / "domain.sqlite")
    MANUALS_DIR : Path = (Path(__file__).resolve().parent.parent / "data" / "manuals")

settings = Settings()



# Explicit bridge to os.environ: Langfuse's CallbackHandler reads credentials
# directly from os.environ, not from the pydantic settings object.
# We set both LANGFUSE_HOST (legacy) and LANGFUSE_BASE_URL (canonical SDK name)
# so whichever version of the SDK is installed will find the right variable.
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)
os.environ.setdefault("LANGFUSE_HOST", settings.LANGFUSE_HOST)
if settings.LANGFUSE_BASE_URL:
    os.environ.setdefault("LANGFUSE_BASE_URL", settings.LANGFUSE_BASE_URL)
else:
    os.environ.setdefault("LANGFUSE_BASE_URL", settings.LANGFUSE_HOST)