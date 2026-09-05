import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


def normalize_database_url(value: str) -> str:
    """Use the installed psycopg v3 driver for unqualified PostgreSQL URLs."""
    parsed = make_url(value)
    if parsed.drivername in {"postgres", "postgresql", "postgresql+psycopg2"}:
        return str(parsed.set(drivername="postgresql+psycopg"))
    return value


def _resolve_default_path(env_var: str, relative_parts: list[str]) -> Path:
    env_value = os.getenv(env_var)
    if env_value:
        return Path(env_value).expanduser()

    repo_root = Path(__file__).resolve().parents[3]
    default_path = repo_root.joinpath(*relative_parts)
    if default_path.exists():
        return default_path

    for base in (Path.cwd(), Path(__file__).resolve().parents[2], repo_root):
        candidate = base.joinpath(*relative_parts)
        if candidate.exists():
            return candidate

    return default_path


def get_default_dataset_path() -> Path:
    return _resolve_default_path("DATASET_PATH", ["data", "generated", "orders.csv"])


def get_default_artifact_path() -> Path:
    return _resolve_default_path("ARTIFACT_PATH", ["data", "generated", "models", "rto_predictor.joblib"])


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(
        default="postgresql+psycopg://revenue_user:revenue_password@localhost:5432/revenue_recovery",
        alias="DATABASE_URL",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    llm_model: str = Field(default="llama3.2:latest", alias="LLM_MODEL")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    max_agent_steps: int = Field(default=8, alias="MAX_AGENT_STEPS")
    llm_request_timeout_seconds: float = Field(default=120.0, alias="LLM_REQUEST_TIMEOUT_SECONDS")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    dataset_path: Path = Field(default_factory=get_default_dataset_path, alias="DATASET_PATH")
    artifact_path: Path = Field(default_factory=get_default_artifact_path, alias="ARTIFACT_PATH")
    razorpay_key_id: str | None = Field(default=None, alias="RAZORPAY_KEY_ID")
    razorpay_key_secret: str | None = Field(default=None, alias="RAZORPAY_KEY_SECRET")
    razorpay_enabled: bool = Field(default=False, alias="RAZORPAY_ENABLED")
    razorpay_request_timeout_seconds: float = Field(default=10.0, alias="RAZORPAY_REQUEST_TIMEOUT_SECONDS")
    razorpay_test_order_id: str | None = Field(default=None, alias="RAZORPAY_TEST_ORDER_ID")

    @field_validator("database_url")
    @classmethod
    def use_psycopg_v3(cls, value: str) -> str:
        return normalize_database_url(value)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
