import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.testing import ensure_database, migrate, test_database_url, truncate_all


@pytest.fixture(scope="session")
def db_url() -> str:
    url = test_database_url(get_settings().database_url)
    try:
        ensure_database(url)
    except OperationalError:
        pytest.skip("PostgreSQL not reachable; start it with `docker compose up -d db`")
    migrate(url)
    return url


@pytest.fixture
def db_engine(db_url):
    engine = create_engine(db_url)
    truncate_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def conn(db_engine):
    with db_engine.begin() as connection:
        yield connection


@pytest.fixture(autouse=True)
def _no_live_services(monkeypatch):
    """Tests never use the developer's real API keys or call live AI/routing services."""
    for key in (
        "GEMINI_API_KEY",
        "OLLAMA_MODEL",
        "ORS_API_KEY",
        "TELEGRAM_BOT_TOKEN",
        "SMTP_HOST",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_FROM",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_SMS_FROM",
        "TWILIO_WHATSAPP_FROM",
        "TWILIO_WHATSAPP_JOIN",
        "ADMIN_EMAIL",
        "ADMIN_PHONE",
    ):
        monkeypatch.setenv(key, "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
