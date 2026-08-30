from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(
        default="postgresql+psycopg://revenue_user:revenue_password@localhost:5432/revenue_recovery",
        alias="DATABASE_URL",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    llm_provider: str = Field(default="local", alias="LLM_PROVIDER")
    llm_model: str = Field(default="rule-based-recovery-agent", alias="LLM_MODEL")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    max_agent_steps: int = Field(default=8, alias="MAX_AGENT_STEPS")
    llm_request_timeout_seconds: float = Field(default=20.0, alias="LLM_REQUEST_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
