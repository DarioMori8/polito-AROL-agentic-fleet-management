from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.example", extra="ignore")

    MANUALS_AGENT_URL: str = "http://localhost:8001"

    # nuove, per l'orchestrator
    ORCHESTRATOR_LLM_PROVIDER: str = "ollama"
    ORCHESTRATOR_OLLAMA_BASE_URL: str = "http://localhost:11434"
    ORCHESTRATOR_OLLAMA_MODEL: str
    ORCHESTRATOR_MAX_ITERATIONS: int = 5

settings = Settings()