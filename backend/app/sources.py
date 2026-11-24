"""Load PM2.5 source shares from the reviewed CSV files into `source_shares`."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import SOURCE_SECTORS, District, SourceShare

DATA = Path(__file__).resolve().parent / "data"
STUDIES = DATA / "source_shares_studies.csv"
DSS_DAILY = DATA / "delhi_dss_daily.csv"


def read_rows(path: Path, daily: bool) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            sector = r["sector"].strip()
            if sector not in SOURCE_SECTORS:
                raise ValueError(f"{path.name}: unknown sector {sector!r}")
            out.append(
                {
                    "city": r.get("city", "delhi").strip().lower(),
                    "date": date.fromisoformat(r["date"]) if daily else None,
                    "sector": sector,
                    "share_pct": float(r["share_pct"]),
                    "source_name": r["source_name"].strip(),
                    "source_url": (r.get("source_url") or "").strip() or None,
                    "source_year": int(r["source_year"]) if r.get("source_year") else None,
                    "is_daily": daily,
                    "note": (r.get("note") or "").strip() or None,
                }
            )
    return out


STUDY_TOLERANCE = 0.5
# IITM DSS daily values, as published, add up to ~101% (their rounding of 29 sources).
DAILY_TOLERANCE = 1.5


def check_sums(rows: list[dict]) -> None:
    """Every (city, date) set must add up to 100 within its source's rounding."""
    totals: dict = {}
    for r in rows:
        key = (r["city"], r["date"])
        totals[key] = totals.get(key, 0.0) + r["share_pct"]
    bad = {
        k: round(v, 2)
        for k, v in totals.items()
        if abs(v - 100) > (DAILY_TOLERANCE if k[1] is not None else STUDY_TOLERANCE)
    }
    if bad:
        raise ValueError(f"shares do not sum to 100: {bad}")


def load(session: Session) -> int:
    rows = read_rows(STUDIES, daily=False) + read_rows(DSS_DAILY, daily=True)
    check_sums(rows)
    ids = dict(session.execute(select(District.slug, District.id)).all())
    now = datetime.now(UTC)
    values = [
        {
            **{k: v for k, v in r.items() if k != "city"},
            "district_id": ids[r["city"]],
            "loaded_at": now,
        }
        for r in rows
        if r["city"] in ids
    ]
    if not values:
        return 0
    stmt = insert(SourceShare).values(values)
    session.execute(
        stmt.on_conflict_do_update(
            constraint="uq_source_shares",
            set_={
                k: stmt.excluded[k] for k in values[0] if k not in ("district_id", "date", "sector")
            },
        )
    )
    session.commit()
    return len(values)
