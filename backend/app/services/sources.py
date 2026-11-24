"""Pollution-source shares for the Air tab."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import District, SourceShare

LABELS = {
    "transport": "Transport",
    "household_fuel": "Household fuel",
    "industry": "Industry",
    "power_plants": "Power plants",
    "dust": "Dust (road + construction)",
    "road_dust": "Road dust",
    "construction_demolition": "Construction",
    "waste_burning": "Waste burning",
    "diesel_gensets": "Diesel generators",
    "brick_kilns": "Brick kilns",
    "stubble_fires": "Stubble and biomass burning",
    "sea_salt": "Sea salt",
    "outside_city": "From outside the city",
    "other": "Other",
}
DAILY_MAX_AGE = timedelta(days=2)


def normalise(shares: dict[str, float]) -> dict[str, float]:
    """Scale to exactly 100.0 (one decimal); the rounding remainder goes to the largest."""
    total = sum(shares.values())
    if total <= 0:
        return {}
    scaled = {k: round(v * 100 / total, 1) for k, v in shares.items()}
    remainder = round(100.0 - sum(scaled.values()), 1)
    if remainder:
        top = max(scaled, key=scaled.get)
        scaled[top] = round(scaled[top] + remainder, 1)
    return scaled


def sources_for(session: Session, district: District, today: date) -> dict:
    daily_date = session.execute(
        select(SourceShare.date)
        .where(
            SourceShare.district_id == district.id,
            SourceShare.is_daily,
            SourceShare.date >= today - DAILY_MAX_AGE,
            SourceShare.date <= today,
        )
        .order_by(SourceShare.date.desc())
        .limit(1)
    ).scalar()
    query = select(SourceShare).where(SourceShare.district_id == district.id)
    query = (
        query.where(SourceShare.date == daily_date)
        if daily_date
        else query.where(SourceShare.date.is_(None))
    )
    rows = session.execute(query).scalars().all()
    if not rows:
        return {
            "kind": None,
            "sectors": [],
            "date": None,
            "source_name": None,
            "source_url": None,
            "source_year": None,
            "published_sum": None,
            "note": None,
            "loaded_at": None,
        }
    published = {r.sector: r.share_pct for r in rows}
    scaled = normalise(published)
    sectors = sorted(
        (
            {"sector": k, "label": LABELS.get(k, k), "share_pct": v, "published_pct": published[k]}
            for k, v in scaled.items()
        ),
        key=lambda s: -s["share_pct"],
    )
    first = rows[0]
    return {
        "kind": "daily" if daily_date else "study",
        "sectors": sectors,
        "date": daily_date,
        "source_name": first.source_name,
        "source_url": first.source_url,
        "source_year": first.source_year,
        "published_sum": round(sum(published.values()), 1),
        "note": first.note,
        "loaded_at": max(r.loaded_at for r in rows),
    }
