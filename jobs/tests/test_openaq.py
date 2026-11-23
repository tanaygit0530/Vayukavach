from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import Reading, Station
from collectors import openaq
from collectors.common import RateLimit, RunStats
from tests.conftest import fixture_router, load, mock_http

NOW = datetime(2026, 11, 23, 12, 45, tzinfo=UTC)


@pytest.fixture
def frozen(monkeypatch):
    monkeypatch.setattr(openaq, "utc_now", lambda: NOW)


def test_parse_hours_skips_negative_and_flags_over_999():
    rows = openaq.parse_hours(load("openaq_hours_pm25.json")["results"], 1, "pm25", NOW)
    hours = {r["hour"].hour: r for r in rows}
    assert 6 not in hours  # negative value = instrument error, not stored as a reading
    assert hours[7]["status"] == "excluded_over_999"
    assert hours[0]["status"] == "ok" and hours[0]["value"] == 182.0


def test_parse_hours_converts_ppm():
    rows = openaq.parse_hours(load("openaq_hours_co.json")["results"], 1, "co", NOW)
    assert rows[0]["unit"] == "mg/m3"
    assert rows[0]["value"] == pytest.approx(1.2 * 28.01 / 24.45)


def test_run_backfills_and_records_gaps(session, districts, api_keys, frozen):
    delhi = [d for d in districts if d.slug == "delhi"]
    stats = RunStats()
    openaq.run(session, mock_http(fixture_router), delhi, stats)
    session.commit()

    stations = {s.external_id: s for s in session.execute(select(Station)).scalars()}
    assert stations["8118"].is_active and not stations["9999"].is_active

    pm25 = (
        session.execute(select(Reading).where(Reading.pollutant == "pm25").order_by(Reading.hour))
        .scalars()
        .all()
    )
    # window = datetimeFirst 00:30 .. floor(now) 12:30 UTC -> 12 hours, all present as rows
    assert len(pm25) == 12
    by_hour = {r.hour.hour: r for r in pm25}
    assert by_hour[3].status == "missing" and by_hour[3].value is None
    assert by_hour[3].reason == "absent_in_openaq"
    assert by_hour[6].status == "missing"  # negative value dropped -> gap
    assert by_hour[7].status == "excluded_over_999"
    co = session.execute(select(Reading).where(Reading.pollutant == "co")).scalars().all()
    assert len(co) == 12 and sum(r.status == "ok" for r in co) == 3
    assert stats.skipped is False


def test_rerun_resumes_after_last_real_value(session, districts, api_keys, frozen):
    delhi = [d for d in districts if d.slug == "delhi"]
    openaq.run(session, mock_http(fixture_router), delhi, RunStats())
    session.commit()
    seen: list[str] = []

    def spy(request):
        seen.append(str(request.url))
        return fixture_router(request)

    openaq.run(session, mock_http(spy), delhi, RunStats())
    pm25_call = next(u for u in seen if "/sensors/23534/hours" in u)
    # last real pm25 value is 07:30 UTC (excluded but real), so it resumes at 08:30
    assert "datetime_from=2026-11-23T08%3A30%3A00Z" in pm25_call


def test_budget_stops_cleanly(session, districts, api_keys, frozen):
    delhi = [d for d in districts if d.slug == "delhi"]
    stats = RunStats()
    openaq.run(session, mock_http(fixture_router, rate_limit=RateLimit(budget=2)), delhi, stats)
    assert any("budget" in n for n in stats.notes)


def test_without_key_is_skipped(session, districts, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("OPENAQ_API_KEY", "")
    get_settings.cache_clear()
    stats = RunStats()
    openaq.run(session, mock_http(fixture_router), districts, stats)
    get_settings.cache_clear()
    assert stats.skipped
