from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.common import cache, get_http, get_now, get_session
from app.main import app
from tests.seed import NOW, seed_all  # noqa: F401  (NOW is imported by API tests)


@pytest.fixture
def seeded(db_engine):
    return seed_all(db_engine)


def geocode_and_map(request: httpx.Request) -> httpx.Response:
    if request.url.host == "geocoding-api.open-meteo.com":
        return httpx.Response(200, json={"results": [
            {"name": "New Delhi", "admin1": "Delhi", "admin2": "New Delhi", "latitude": 28.6139,
             "longitude": 77.209, "population": 317797, "country_code": "IN"},
            {"name": "Leh", "admin1": "Ladakh", "admin2": "Leh", "latitude": 34.16,
             "longitude": 77.58, "population": 30870, "country_code": "IN"},
        ]})  # fmt: skip
    if request.url.host == "air-quality-api.open-meteo.com":
        n = len(request.url.params["latitude"].split(","))
        return httpx.Response(200, json=[
            {"current": {"time": "2026-11-08T20:00", "pm2_5": 100.0 + i}} for i in range(n)
        ])  # fmt: skip
    return httpx.Response(404)


@pytest.fixture
def client(db_engine, seeded):
    cache.clear()

    def session_override():
        with Session(db_engine) as s:
            yield s

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_now] = lambda: NOW
    app.dependency_overrides[get_http] = lambda: httpx.Client(
        transport=httpx.MockTransport(geocode_and_map)
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    cache.clear()


def assert_meta(body, label=None):
    for key in ("source", "updated_at", "label", "stale"):
        assert key in body, key
    assert body["source"]
    if body["updated_at"]:
        assert body["updated_at"].endswith("+05:30"), body["updated_at"]
    if label:
        assert body["label"] == label


__all__ = ["NOW", "assert_meta", "date"]
