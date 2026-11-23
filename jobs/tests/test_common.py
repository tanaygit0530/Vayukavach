from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.models import FetchLog
from collectors.common import (
    BudgetExhausted,
    HTTPFailure,
    RateLimit,
    concentration_status,
    fetch_run,
    floor_hour,
    hours_between,
    to_standard_unit,
)
from tests.conftest import mock_http


def test_floor_hour_uses_ist_hour_grid():
    ist = timezone(timedelta(hours=5, minutes=30))
    # 00:45 IST on 9 Nov -> hour starting 00:00 IST = 18:30 UTC on 8 Nov
    assert floor_hour(datetime(2026, 11, 9, 0, 45, tzinfo=ist)) == datetime(
        2026, 11, 8, 18, 30, tzinfo=UTC
    )
    # 10:10 UTC is 15:40 IST -> 15:00 IST = 09:30 UTC
    assert floor_hour(datetime(2026, 11, 8, 10, 10, tzinfo=UTC)) == datetime(
        2026, 11, 8, 9, 30, tzinfo=UTC
    )


def test_floor_hour_is_idempotent():
    h = floor_hour(datetime(2026, 11, 8, 10, 10, tzinfo=UTC))
    assert floor_hour(h) == h


def test_floor_hour_rejects_naive():
    with pytest.raises(ValueError):
        floor_hour(datetime(2026, 1, 1))


def test_hours_between_is_half_open():
    start = datetime(2026, 1, 1, 0, 30, tzinfo=UTC)  # 06:00 IST, on the hour grid
    hours = list(hours_between(start, start + timedelta(hours=3)))
    assert hours == [start + timedelta(hours=i) for i in range(3)]


@pytest.mark.parametrize(
    ("pollutant", "value", "unit", "expected"),
    [
        ("pm25", 100.0, "µg/m³", (100.0, "ug/m3")),
        ("pm25", 100.0, "μg/m³", (100.0, "ug/m3")),  # Greek mu
        ("co", 1.0, "ppm", (1.0 * 1000 * 28.01 / 24.45 / 1000, "mg/m3")),
        ("co", 1500.0, "µg/m³", (1.5, "mg/m3")),
        ("no2", 10.0, "ppb", (10.0 * 46.01 / 24.45, "ug/m3")),
        ("o3", 0.05, "ppm", (50.0 * 48.0 / 24.45, "ug/m3")),
    ],
)
def test_to_standard_unit(pollutant, value, unit, expected):
    got_value, got_unit = to_standard_unit(pollutant, value, unit)
    assert got_unit == expected[1]
    assert got_value == pytest.approx(expected[0])


def test_to_standard_unit_rejects_unknown():
    with pytest.raises(ValueError):
        to_standard_unit("pm25", 1.0, "furlongs")


def test_excluded_over_999():
    assert concentration_status("pm25", 999.0, "ug/m3") == "excluded_over_999"
    assert concentration_status("pm25", 998.9, "ug/m3") == "ok"
    assert concentration_status("co", 1200.0, "mg/m3") == "ok"


def test_rate_limit_spaces_calls_and_enforces_budget():
    now = [0.0]
    slept: list[float] = []

    def sleep(s):
        slept.append(s)
        now[0] += s

    rl = RateLimit(per_minute=60, budget=3, sleep=sleep, clock=lambda: now[0])
    rl.acquire()
    rl.acquire()
    rl.acquire()
    assert slept == [pytest.approx(1.0), pytest.approx(1.0)]
    with pytest.raises(BudgetExhausted):
        rl.acquire()


def test_http_retries_server_errors_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    assert mock_http(handler).get_json("https://example.test/x") == {"ok": True}
    assert calls["n"] == 3


def test_http_retries_429():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(429) if calls["n"] == 1 else httpx.Response(200, json=[])

    assert mock_http(handler).get_json("https://example.test/x") == []


def test_http_gives_up_after_attempts():
    http = mock_http(lambda r: httpx.Response(500), attempts=2)
    with pytest.raises(Exception, match="HTTP 500"):
        http.get_json("https://example.test/x")


def test_http_does_not_retry_client_errors():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(403)

    with pytest.raises(HTTPFailure):
        mock_http(handler).get_json("https://example.test/x")
    assert calls["n"] == 1


def test_errors_never_contain_api_keys():
    http = mock_http(lambda r: httpx.Response(403), attempts=1)
    with pytest.raises(HTTPFailure) as exc:
        http.get_json("https://api.data.gov.in/resource/x", {"api-key": "SECRET123", "limit": 5})
    assert "SECRET123" not in str(exc.value)
    assert "api-key=%2A%2A%2A" in str(exc.value) or "api-key=***" in str(exc.value)
    assert "limit=5" in str(exc.value)


def test_retryable_errors_are_redacted_too():
    http = mock_http(lambda r: httpx.Response(503), attempts=1)
    with pytest.raises(HTTPFailure) as exc:
        http.get_json("https://api.data.gov.in/x", {"api-key": "SECRET123"})
    assert "SECRET123" not in str(exc.value)


def test_fetch_run_logs_success(session):
    with fetch_run(session, "demo") as stats:
        stats.rows = 5
    log = session.execute(select(FetchLog)).scalar_one()
    assert (log.status, log.rows, log.errors) == ("ok", 5, 0)
    assert log.finished_at is not None


def test_fetch_run_logs_failure_and_reraises(session):
    with pytest.raises(RuntimeError):
        with fetch_run(session, "demo"):
            raise RuntimeError("boom")
    log = session.execute(select(FetchLog)).scalar_one()
    assert log.status == "failed"
    assert "boom" in log.detail
    assert log.errors == 1


def test_upsert_counts_rows_written(session, districts):
    from app.models import District
    from collectors.common import upsert

    rows = [{"slug": "x1", "name": "X", "state": "S", "lat": 1.0, "lon": 1.0}]
    assert upsert(session, District.__table__, rows, ["slug"]) == 1
    assert upsert(session, District.__table__, rows, ["slug"], do_nothing=True) == 0
    assert upsert(session, District.__table__, rows, ["slug"]) == 1  # update counts


def test_per_request_headers_do_not_stick_to_the_client():
    seen = []

    def handler(request):
        seen.append(request.headers.get("X-API-Key"))
        return httpx.Response(200, json={})

    http = mock_http(handler)
    http.get_json("https://api.openaq.org/x", headers={"X-API-Key": "SECRET"})
    http.get_json("https://api.open-meteo.com/y")
    assert seen == ["SECRET", None]
