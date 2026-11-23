from datetime import date, timedelta

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analysis.summary import build_recent
from app.analysis.time import day_bounds
from app.api.common import cache, get_http, get_now, get_session
from app.main import app
from tests.analysis.helpers import DAY
from tests.seed import seed_delhi

NOW = day_bounds(DAY)[0] + timedelta(hours=20, minutes=30)  # 20:30 IST on the seeded day


def _seed_weather(conn, district_id, base_temp):
    start = day_bounds(DAY)[0]
    for h in range(48):
        hour = start + timedelta(hours=h)
        local = h % 24
        temp = base_temp + 8 * np.sin((local - 8) / 24 * 2 * np.pi)
        conn.execute(
            text(
                "INSERT INTO weather (district_id, hour, temperature, apparent_temperature,"
                " humidity, dew_point, wind_speed, wind_gusts, wind_direction, pressure,"
                " cloud_cover, precipitation, precipitation_probability, visibility, uv_index,"
                " weather_code, boundary_layer_height, is_forecast, fetched_at) VALUES"
                " (:d, :h, :t, :a, 60, 12, 4, 9, 300, 1012, 10, 0, 5, 3500, :uv, 0, 250, :f,"
                " :fetched)"
            ),
            {"d": district_id, "h": hour, "t": float(temp), "a": float(temp + 1.5),
             "uv": float(max(0, 8 * np.sin((local - 6) / 12 * np.pi))) if 6 <= local <= 18
             else 0.0, "f": hour > NOW, "fetched": NOW - timedelta(minutes=20)},
        )  # fmt: skip
    for i in range(10):
        day = DAY + timedelta(days=i)
        sunrise = day_bounds(day)[0] + timedelta(hours=6, minutes=40)
        conn.execute(
            text(
                "INSERT INTO weather_daily (district_id, date, weather_code, temperature_max,"
                " temperature_min, apparent_temperature_max, apparent_temperature_min, sunrise,"
                " sunset, daylight_duration, uv_index_max, precipitation_sum,"
                " precipitation_probability_max, is_forecast, fetched_at) VALUES"
                " (:d, :day, 1, :tmax, :tmin, :tmax, :tmin, :sr, :ss, 38000, 6.5, 0, 10, :f,"
                " :fetched)"
            ),
            {"d": district_id, "day": day, "tmax": base_temp + 8, "tmin": base_temp - 8,
             "sr": sunrise, "ss": sunrise + timedelta(hours=10, minutes=40), "f": i > 0,
             "fetched": NOW - timedelta(minutes=20)},
        )  # fmt: skip


@pytest.fixture
def seeded(db_engine):
    with db_engine.begin() as conn:
        delhi = seed_delhi(conn)
        shimla = conn.execute(
            text(
                "INSERT INTO districts (slug, name, state, lat, lon) VALUES ('shimla', 'Shimla',"
                " 'Himachal Pradesh', 31.1, 77.17) RETURNING id"
            )  # fmt: skip
        ).scalar_one()
        start = day_bounds(DAY)[0]
        for h in range(-24, 72):
            hour = start + timedelta(hours=h)
            for pollutant, value in (("pm25", 40.0), ("pm10", 60.0), ("no2", 20.0),
                                     ("co2", 430.0)):  # fmt: skip
                conn.execute(
                    text(
                        "INSERT INTO model_air (district_id, lat, lon, hour, pollutant, value,"
                        " unit, model_run, is_forecast, fetched_at) VALUES (:d, 31.1, 77.2, :h,"
                        " :p, :v, :u, :h, :f, :h) ON CONFLICT DO NOTHING"
                    ),
                    {"d": shimla, "h": hour, "p": pollutant, "v": value,
                     "u": "ppm" if pollutant == "co2" else "ug/m3", "f": hour > NOW},
                )  # fmt: skip
        _seed_weather(conn, delhi, 26.0)
        _seed_weather(conn, shimla, 9.0)
    with Session(db_engine) as session:
        build_recent(session, days=1, now=NOW)
    return {"delhi": delhi, "shimla": shimla}


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
