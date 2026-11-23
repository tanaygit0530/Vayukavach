"""District list: loaded from a CSV (configurable with DISTRICTS_FILE) and kept in sync."""

import csv
import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import District
from collectors.common import haversine_km, upsert

DEFAULT_FILE = Path(__file__).resolve().parents[1] / "config" / "districts.csv"


@dataclass(frozen=True)
class DistrictRow:
    id: int
    slug: str
    name: str
    lat: float
    lon: float


def load_csv(path: Path | None = None) -> list[dict]:
    path = Path(path or os.environ.get("DISTRICTS_FILE") or DEFAULT_FILE)
    with path.open(newline="", encoding="utf-8") as f:
        rows = [
            {
                "slug": r["slug"].strip(),
                "name": r["name"].strip(),
                "state": r["state"].strip(),
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
            }
            for r in csv.DictReader(f)
        ]
    if not rows:
        raise ValueError(f"no districts in {path}")
    return rows


def sync_districts(session: Session, path: Path | None = None) -> list[DistrictRow]:
    """Upsert the configured districts and return them (only the configured ones)."""
    rows = load_csv(path)
    upsert(session, District.__table__, rows, ["slug"])
    slugs = [r["slug"] for r in rows]
    found = session.execute(select(District).where(District.slug.in_(slugs))).scalars()
    return [DistrictRow(d.id, d.slug, d.name, d.lat, d.lon) for d in found]


def nearest_district(
    districts: list[DistrictRow], lat: float | None, lon: float | None, max_km: float = 30.0
) -> int | None:
    if lat is None or lon is None or not districts:
        return None
    best = min(districts, key=lambda d: haversine_km(lat, lon, d.lat, d.lon))
    return best.id if haversine_km(lat, lon, best.lat, best.lon) <= max_km else None
