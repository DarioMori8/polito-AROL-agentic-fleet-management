import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    MANUALS_AGENT_URL: str = "http://localhost:8001"

    # nuove, per l'orchestrator
    ORCHESTRATOR_LLM_PROVIDER: str = "ollama"
    ORCHESTRATOR_OLLAMA_BASE_URL: str = "http://localhost:11434"
    ORCHESTRATOR_OLLAMA_MODEL: str
    ORCHESTRATOR_MAX_ITERATIONS: int = 5
    ORCHESTRATOR_NUM_CTX: int = 4096


    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_SECRET_KEY: str
    LANGFUSE_HOST: str = "http://localhost:3000"

    CHECKPOINT_DB_PATH: str = str(Path(__file__).resolve().parent.parent / "data" / "checkpoints.sqlite")
    DOMAIN_DB_PATH: str = str(Path(__file__).resolve().parent.parent / "data" / "domain.sqlite")
settings = Settings()



# Ponte esplicito verso os.environ: CallbackHandler() di Langfuse legge le
# credenziali direttamente da os.environ, non dall'oggetto `settings` di
# pydantic — che invece le ha lette dal .env nel proprio modello interno,
# senza esportarle automaticamente nell'ambiente di processo. Senza
# questo blocco, settings.LANGFUSE_PUBLIC_KEY sarebbe valorizzato
# correttamente ma CallbackHandler() vedrebbe comunque variabili vuote.
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)
os.environ.setdefault("LANGFUSE_HOST", settings.LANGFUSE_HOST)