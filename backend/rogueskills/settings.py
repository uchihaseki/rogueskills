from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ROGUESKILLS_",
        env_file=".env",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 5173
    database_url: str = Field(default=f"sqlite:///{PROJECT_ROOT / 'data' / 'rogueskills.db'}")
    github_token: str | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = 60
    search_cache_ttl_seconds: int = 60
    automatic_run_step_delay_seconds: float = Field(default=0.35, ge=0, le=5)
    max_request_bytes: int = 2_000_000
    cors_origins: list[str] = ["http://localhost:5174", "http://127.0.0.1:5174"]
    project_root: Path = PROJECT_ROOT


settings = Settings()
