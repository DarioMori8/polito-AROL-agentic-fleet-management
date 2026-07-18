from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    LLM_PROVIDER: str = "ollama"  

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str 

    # Other examples:
    # ANTHROPIC_API_KEY: str | None = None
    # ANTHROPIC_MODEL: str = "claude-sonnet-5" 

    MAX_ITERATIONS: int = 5


settings = Settings()