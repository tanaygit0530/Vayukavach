"""Application settings, read from environment variables or the repo-root .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://vayu:vayu@localhost:5433/vayukavach"
    data_gov_in_api_key: str = ""
    openaq_api_key: str = ""
    gemini_api_key: str = ""
    telegram_bot_token: str = ""
    ors_api_key: str = ""  # optional: OpenRouteService; without it routes use public OSRM
    frontend_origin: str = "http://localhost:5180"
    rate_limit_per_minute: int = 300  # one Air page load makes ~10 calls


@lru_cache
def get_settings() -> Settings:
    return Settings()
