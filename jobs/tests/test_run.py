from datetime import UTC, datetime

import httpx
from sqlalchemy import func, select

import run
from app.models import District, FetchLog, Reading
from collectors import openaq
from tests.conftest import fixture_router, mock_http


def test_no_args_prints_usage(capsys):
    assert run.main(["run.py"]) == 0
    assert "usage" in capsys.readouterr().out


def test_unknown_job_fails():
    assert run.main(["run.py", "does-not-exist"]) == 1


def test_hourly_runs_every_collector_and_logs_each(session, api_keys, monkeypatch):
    monkeypatch.setattr(openaq, "utc_now", lambda: datetime(2026, 11, 23, 12, 45, tzinfo=UTC))
    results = run.run_collectors(session, run.GROUPS["hourly"], lambda name: mock_http(
        fixture_router))  # fmt: skip
    assert results == {
        "cpcb": "ok", "openmeteo-air": "ok", "weather": "ok", "openaq": "ok", "summarize": "ok"
    }  # fmt: skip
    assert session.scalar(select(func.count()).select_from(District)) == 10
    logs = session.execute(select(FetchLog.source, FetchLog.status)).all()
    assert sorted(logs) == sorted((k, "ok") for k in results)
    assert session.scalar(select(func.count()).select_from(Reading)) > 0


def test_one_failing_collector_does_not_stop_the_others(session, api_keys):
    def handler(request):
        if request.url.host == "api.data.gov.in":
            return httpx.Response(500)
        return fixture_router(request)

    results = run.run_collectors(
        session, ["cpcb", "weather"], lambda name: mock_http(handler, attempts=2)
    )
    assert results == {"cpcb": "failed", "weather": "ok"}
    failed = session.execute(select(FetchLog).where(FetchLog.source == "cpcb")).scalar_one()
    assert failed.status == "failed" and "HTTP 500" in failed.detail


def test_missing_keys_are_logged_as_skipped_not_failed(session, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("DATA_GOV_IN_API_KEY", "")
    get_settings.cache_clear()
    results = run.run_collectors(session, ["cpcb"], lambda name: mock_http(fixture_router))
    get_settings.cache_clear()
    assert results == {"cpcb": "skipped"}
    log = session.execute(select(FetchLog)).scalar_one()
    assert log.status == "skipped" and "DATA_GOV_IN_API_KEY" in log.detail


def test_main_keeps_request_urls_out_of_logs(monkeypatch):
    import logging

    monkeypatch.setattr(run, "run_collectors", lambda session, names: {"cpcb": "ok"})
    monkeypatch.setattr("app.db.SessionLocal", lambda: _NullSession())
    run.main(["run.py", "cpcb"])
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


class _NullSession:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
