from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.example", extra="ignore")

    MANUALS_AGENT_URL: str = "http://localhost:8001"

settings = Settings()