import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.testing import ensure_database, migrate, test_database_url, truncate_all
from collectors.common import HttpClient
from collectors.districts import sync_districts

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


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
def session(db_url):
    engine = create_engine(db_url)
    truncate_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


@pytest.fixture
def districts(session):
    rows = sync_districts(session)
    session.commit()
    return rows


@pytest.fixture
def api_keys(monkeypatch):
    monkeypatch.setenv("DATA_GOV_IN_API_KEY", "test-key")
    monkeypatch.setenv("OPENAQ_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


Handler = Callable[[httpx.Request], httpx.Response]


def mock_http(handler: Handler, **kwargs) -> HttpClient:
    """HttpClient backed by an in-memory transport: no network in tests."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return HttpClient(client=client, max_wait=0, **kwargs)


def _per_location(request: httpx.Request, name: str):
    """Open-Meteo returns one result per requested coordinate. The recording has two
    (Delhi, Kanpur); reuse them in turn, with each requested coordinate filled in."""
    recorded = load(name)
    lats = request.url.params["latitude"].split(",")
    lons = request.url.params["longitude"].split(",")
    out = []
    for i, (lat, lon) in enumerate(zip(lats, lons, strict=True)):
        loc = dict(recorded[i % len(recorded)])
        loc["latitude"], loc["longitude"] = float(lat), float(lon)
        out.append(loc)
    return out if len(out) > 1 else out[0]


def fixture_router(request: httpx.Request) -> httpx.Response:
    """Serve recorded responses by URL."""
    host, path = request.url.host, request.url.path
    if host == "api.data.gov.in":
        return httpx.Response(200, json=load("cpcb_delhi.json"))
    if host == "air-quality-api.open-meteo.com":
        return httpx.Response(200, json=_per_location(request, "openmeteo_air_delhi_kanpur.json"))
    if host == "api.open-meteo.com":
        return httpx.Response(200, json=_per_location(request, "openmeteo_wx_delhi_kanpur.json"))
    if host == "api.openaq.org":
        if path == "/v3/locations":
            return httpx.Response(200, json=load("openaq_locations_delhi.json"))
        if path == "/v3/sensors/23534/hours":
            return httpx.Response(200, json=load("openaq_hours_pm25.json"))
        if path == "/v3/sensors/23535/hours":
            return httpx.Response(200, json=load("openaq_hours_co.json"))
    return httpx.Response(404, json={"detail": f"no fixture for {request.url}"})
