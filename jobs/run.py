"""Entry point for scheduled jobs: `uv run python run.py <job>`.

Jobs:
  cpcb           CPCB real-time snapshot (data.gov.in)
  openaq         OpenAQ v3 station history (90-day backfill, then incremental)
  openmeteo-air  Open-Meteo CAMS air model, 5-day forecast
  weather        Open-Meteo weather, hourly + daily, 16-day forecast
  summarize      completeness, gap flags, measured/shadow/official AQI for the last
                 SUMMARY_DAYS IST days (default 2) -> daily_city_summary
  history        one-off: ~2 years of daily AQI (OpenAQ daily means) + CAMS/weather features
  forecast       nightly: recent daily AQI + features, backtest gate, retrain, 10-day forecast
  backtest       full 12-month backtest -> docs/models/backtest.md
  sources        load pollution-source shares from backend/app/data/*.csv
  hourly         all of the above, each logged separately in fetch_log
  cloud          all except cpcb (for GitHub-hosted runners)

Exit code is 1 if any collector failed, so GitHub Actions marks the run red.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy.orm import Session

from collectors import cpcb, history, openaq, openmeteo
from collectors.common import HttpClient, RateLimit, fetch_run
from collectors.districts import sync_districts

log = logging.getLogger("vayukavach.jobs")

Collector = Callable[..., None]


def _http_for(name: str) -> HttpClient:
    if name in {"openaq", "history", "forecast"}:
        return HttpClient(
            rate_limit=RateLimit(per_minute=openaq.REQUESTS_PER_MINUTE, budget=openaq.RUN_BUDGET)
        )
    return HttpClient()


def summarize(session: Session, http: HttpClient, districts, stats) -> None:
    from app.analysis.summary import build_recent

    rows = build_recent(session, days=int(os.environ.get("SUMMARY_DAYS", "2")))
    stats.rows += len(rows)
    flagged = [f"{r['district_id']}:{r['date']}" for r in rows if r["gap_bias_flag"]]
    if flagged:
        stats.notes.append(f"gap-bias flags: {', '.join(flagged)}")


def forecast(session: Session, http: HttpClient, districts, stats) -> None:
    """Nightly: recent daily AQI + features, backtest gate, retrain, write 10-day forecasts."""
    from app.forecast.serve import run_nightly

    history.daily_aqi_from_readings(session, districts, stats)
    history.refresh_features(session, http, districts, stats)
    result = run_nightly(session, weeks=int(os.environ.get("BACKTEST_WEEKS", "52")))
    s = result.summary
    stats.rows += result.rows_written
    stats.notes.append(
        f"{result.version}: days1-5 MAE {s['days_1_5']['cams_corrected']:.1f} "
        f"(raw {s['days_1_5']['cams_raw']:.1f}, persistence {s['days_1_5']['persistence']:.1f}); "
        f"days6-10 MAE {s['days_6_10']['outlook']:.1f} "
        f"(persistence {s['days_6_10']['persistence']:.1f}); "
        f"bias ok={s['bias_beats_baseline']} outlook ok={s['outlook_beats_baseline']}"
    )


def backtest_report(session: Session, http: HttpClient, districts, stats) -> None:
    """Full 12-month backtest -> docs/models/backtest.md (run locally, then commit)."""
    from pathlib import Path

    from app.forecast.model import backtest, report_markdown, summary
    from app.forecast.serve import load_frame, today_ist
    from collectors.common import utc_now

    today = today_ist(utc_now())
    df = load_frame(session)
    bt = backtest(df[df["date"] < today], end=today - timedelta(days=1), weeks=52)
    out = Path(__file__).resolve().parents[1] / "docs" / "models" / "backtest.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report_markdown(bt, summary(bt)), encoding="utf-8")
    stats.notes.append(f"wrote {out}")


def load_sources(session: Session, http: HttpClient, districts, stats) -> None:
    """Reviewed CSVs (studies + manually entered Delhi DSS days) -> source_shares."""
    from app.sources import load

    stats.rows += load(session)


def alerts(session: Session, http: HttpClient, districts, stats) -> None:
    """Daily 7 AM summaries, instant AQI/heat alerts and collector-failure notices. Safe to run
    from the Mac and the cloud in the same hour: sends are de-duplicated per subscription."""
    from app.alerts.channels import Sender, available
    from app.alerts.service import run
    from collectors.common import utc_now

    if not any(available().values()):
        stats.skipped = True
        stats.notes.append("no alert channel configured (SMTP / Twilio)")
        return
    r = run(session, Sender(), utc_now())
    stats.rows = sum(r.sent.values())
    stats.errors = r.failed
    stats.notes.append(f"sent {r.sent}, failed {r.failed}, admin {r.admin or '-'}")


COLLECTORS: dict[str, Collector] = {
    "cpcb": cpcb.run,
    "openaq": openaq.run,
    "openmeteo-air": openmeteo.run_air,
    "weather": openmeteo.run_weather,
    "summarize": summarize,
    "history": history.run_backfill,
    "forecast": forecast,
    "backtest": backtest_report,
    "sources": load_sources,
    "alerts": alerts,
}
GROUPS = {
    "hourly": ["cpcb", "openmeteo-air", "weather", "openaq", "summarize", "alerts"],
    # GitHub-hosted runners: data.gov.in refuses connections from them (checked 2026-11-23),
    # so CPCB runs from a machine in India (jobs/scripts/install_cpcb_launchd.sh).
    "cloud": ["openmeteo-air", "weather", "openaq", "summarize", "alerts"],
}
JOBS = sorted([*COLLECTORS, *GROUPS])


def run_collectors(
    session: Session,
    names: list[str],
    http_factory: Callable[[str], HttpClient] = _http_for,
) -> dict[str, str]:
    """Run collectors one by one; a failure in one does not stop the others."""
    districts = sync_districts(session)
    session.commit()
    results: dict[str, str] = {}
    for name in names:
        try:
            with fetch_run(session, name) as stats:
                COLLECTORS[name](session, http_factory(name), districts, stats)
            results[name] = "skipped" if stats.skipped else "ok"
            log.info("%s: %s rows=%s %s", name, results[name], stats.rows, "; ".join(stats.notes))
        except Exception:
            log.exception("%s failed", name)
            results[name] = "failed"
    return results


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(f"usage: run.py <job>   available: {', '.join(JOBS)}")
        return 0
    job = argv[1]
    if job not in COLLECTORS and job not in GROUPS:
        print(f"unknown job {job!r}; available: {', '.join(JOBS)}")
        return 1
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # httpx logs full URLs at INFO; data.gov.in puts the API key in the query string.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from app.db import SessionLocal

    with SessionLocal() as session:
        results = run_collectors(session, GROUPS.get(job, [job]))
    print(" ".join(f"{k}={v}" for k, v in results.items()))
    return 1 if "failed" in results.values() else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
