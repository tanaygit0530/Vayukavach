"""Entry point for scheduled jobs: `uv run python run.py <job>`.

Jobs:
  cpcb           CPCB real-time snapshot (data.gov.in)
  openaq         OpenAQ v3 station history (90-day backfill, then incremental)
  openmeteo-air  Open-Meteo CAMS air model, 5-day forecast
  weather        Open-Meteo weather, hourly + daily, 16-day forecast
  summarize      completeness, gap flags, measured/shadow/official AQI for the last
                 SUMMARY_DAYS IST days (default 2) -> daily_city_summary
  hourly         all of the above, each logged separately in fetch_log

Exit code is 1 if any collector failed, so GitHub Actions marks the run red.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable

from sqlalchemy.orm import Session

from collectors import cpcb, openaq, openmeteo
from collectors.common import HttpClient, RateLimit, fetch_run
from collectors.districts import sync_districts

log = logging.getLogger("vayukavach.jobs")

Collector = Callable[..., None]


def _http_for(name: str) -> HttpClient:
    if name == "openaq":
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


COLLECTORS: dict[str, Collector] = {
    "cpcb": cpcb.run,
    "openaq": openaq.run,
    "openmeteo-air": openmeteo.run_air,
    "weather": openmeteo.run_weather,
    "summarize": summarize,
}
GROUPS = {"hourly": ["cpcb", "openmeteo-air", "weather", "openaq", "summarize"]}
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
