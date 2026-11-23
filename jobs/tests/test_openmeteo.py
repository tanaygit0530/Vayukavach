from datetime import UTC, datetime

from sqlalchemy import func, select

from app.models import ModelAir, Weather, WeatherDaily
from collectors import openmeteo
from collectors.common import RunStats
from collectors.districts import DistrictRow
from tests.conftest import fixture_router, load, mock_http

FETCHED = datetime(2026, 11, 23, 11, 5, tzinfo=UTC)
TWO = [DistrictRow(1, "delhi", "Delhi", 28.6139, 77.209), DistrictRow(2, "kanpur", "Kanpur",
       26.4499, 80.3319)]  # fmt: skip


def test_parse_air_converts_times_and_co():
    rows = openmeteo.parse_air(load("openmeteo_air_delhi_kanpur.json"), TWO, FETCHED)
    payload = load("openmeteo_air_delhi_kanpur.json")[0]
    # 144 hours x 8 variables x 2 locations
    assert len(rows) == 144 * 8 * 2
    first_co = next(r for r in rows if r["pollutant"] == "co" and r["district_id"] == 1)
    assert first_co["unit"] == "mg/m3"
    assert first_co["value"] == payload["hourly"]["carbon_monoxide"][0] / 1000
    # '2026-11-22T00:00' IST == 2026-11-21 18:30 UTC
    assert first_co["hour"] == datetime(2026, 11, 21, 18, 30, tzinfo=UTC)
    assert first_co["lat"] == round(payload["latitude"], 4)


def test_parse_air_keeps_null_model_values():
    rows = openmeteo.parse_air(load("openmeteo_air_delhi_kanpur.json"), TWO, FETCHED)
    nh3 = [r for r in rows if r["pollutant"] == "nh3"]
    assert nh3 and all(r["value"] is None for r in nh3)  # CAMS global has no NH3 for India


def test_parse_air_marks_forecast_hours():
    rows = openmeteo.parse_air(load("openmeteo_air_delhi_kanpur.json"), TWO, FETCHED)
    assert any(r["is_forecast"] for r in rows) and not all(r["is_forecast"] for r in rows)
    assert all(r["is_forecast"] == (r["hour"] > FETCHED) for r in rows)


def test_parse_weather_hourly_and_daily():
    hourly, daily = openmeteo.parse_weather(load("openmeteo_wx_delhi_kanpur.json"), TWO, FETCHED)
    assert len(hourly) == 408 * 2  # 17 days x 24 h
    assert len(daily) == 17 * 2
    row = next(r for r in hourly if r["district_id"] == 1)
    assert set(openmeteo.HOURLY_WEATHER.values()) <= set(row)
    today = next(d for d in daily if d["district_id"] == 1 and str(d["date"]) == "2026-11-23")
    assert today["is_forecast"] is False
    # sunrise '2026-11-23T06:49' IST -> 01:19 UTC
    assert today["sunrise"] == datetime(2026, 11, 23, 1, 19, tzinfo=UTC)


def test_run_air_and_weather_store_and_are_idempotent(session, districts):
    two = [d for d in districts if d.slug in {"delhi", "kanpur"}]
    http = mock_http(fixture_router)
    for _ in range(2):
        openmeteo.run_air(session, http, two, RunStats())
        openmeteo.run_weather(session, http, two, RunStats())
        session.commit()
    assert session.scalar(select(func.count()).select_from(ModelAir)) == 144 * 8 * 2
    assert session.scalar(select(func.count()).select_from(Weather)) == 408 * 2
    assert session.scalar(select(func.count()).select_from(WeatherDaily)) == 17 * 2
