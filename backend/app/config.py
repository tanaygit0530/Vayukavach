"""Application settings, read from environment variables or the repo-root .env file."""

from datetime import datetime
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
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
    gemini_model: str = "gemini-2.5-flash"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = ""  # e.g. gemma3 or another tool-capable model; empty = disabled
    telegram_bot_token: str = ""
    ors_api_key: str = ""  # optional: OpenRouteService; without it routes use public OSRM
    frontend_origin: str = "http://localhost:5180"
    # public links in alerts (unsubscribe); default = local API
    public_api_url: str = "http://localhost:8000"
    # alerts: email over SMTP (e.g. Gmail: smtp.gmail.com, 587, an app password)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    # alerts: SMS and WhatsApp over Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_sms_from: str = ""  # a Twilio number, e.g. +1...
    twilio_whatsapp_from: str = ""  # sandbox: whatsapp:+14155238886
    twilio_whatsapp_join: str = ""  # sandbox join phrase, shown on the sign-up page
    # who hears about failing collectors (email and/or WhatsApp/SMS number)
    admin_email: str = ""
    admin_phone: str = ""
    rate_limit_per_minute: int = 300  # one Air page load makes ~10 calls
    # Replay: the API answers as if it were this moment (ISO time with zone). For end-to-end
    # tests and demos on a stored day; never set it in production.
    replay_now: datetime | None = None

    @field_validator("replay_now", mode="before")
    @classmethod
    def _blank_is_off(cls, v):
        return None if v in ("", None) else v


@lru_cache
def get_settings() -> Settings:
    return Settings()
