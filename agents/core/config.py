from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    LLM_PROVIDER: str = "ollama"  

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str
    OLLAMA_NUM_CTX: int = 16384
    EMBEDDING_MODEL: str = "nomic-embed-text"

    # Other examples:
    # ANTHROPIC_API_KEY: str | None = None
    # ANTHROPIC_MODEL: str = "claude-sonnet-5"

    MAX_ITERATIONS: int = 5
    CHROMA_PATH: str = "./data/chroma"
    # Read-only mount of the shared manuals volume. Absolute because the
    # ingestion runs inside the container; override it when running locally.
    MANUALS_PATH: str = "/data/manuals"
    DOCS_SERVICE_URL: str = "http://localhost:8003"
    IOT_SERVICE_URL: str = "http://localhost:8003"

    # Use the same Langfuse project as the orchestrator. Without credentials
    # the SDK is a no-op, so agents can still run independently in development.
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "http://localhost:3000"
    LANGFUSE_TRACING_ENABLED: bool = True


settings = Settings()
