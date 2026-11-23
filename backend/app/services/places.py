"""Place search (Open-Meteo Geocoding) and saved-place summaries."""

from __future__ import annotations

from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.shadow import haversine_km
from app.models import District
from app.services.air import air_now
from app.services.weather import weather_now

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
COVERED_KM = 50.0


def search(http: httpx.Client, session: Session, q: str) -> list[dict]:
    response = http.get(
        GEOCODING_URL,
        params={"name": q, "count": 10, "language": "en", "format": "json", "countryCode": "IN"},
    )
    response.raise_for_status()
    districts = session.execute(select(District)).scalars().all()
    out = []
    for r in response.json().get("results") or []:
        if r.get("country_code") not in (None, "IN"):
            continue
        lat, lon = r["latitude"], r["longitude"]
        nearest = min(districts, key=lambda d: haversine_km(lat, lon, d.lat, d.lon), default=None)
        dist = haversine_km(lat, lon, nearest.lat, nearest.lon) if nearest else None
        out.append(
            {
                "name": r.get("name"),
                "state": r.get("admin1"),
                "district": r.get("admin2"),
                "lat": lat,
                "lon": lon,
                "population": r.get("population"),
                "covered_district": nearest.slug if nearest and dist <= COVERED_KM else None,
                "distance_km": round(dist, 1) if dist is not None else None,
            }
        )
    return out


def summary(session: Session, slugs: list[str], now: datetime) -> list[dict]:
    districts = session.execute(select(District).where(District.slug.in_(slugs))).scalars()
    by_slug = {d.slug: d for d in districts}
    out = []
    for slug in slugs:
        d = by_slug.get(slug)
        if d is None:
            continue
        air = air_now(session, d, now)
        wx = weather_now(session, d, now)
        out.append(
            {
                "id": d.slug,
                "name": d.name,
                "state": d.state,
                "aqi": air["aqi"],
                "category": air["category"],
                "category_key": air["category_key"],
                "aqi_label": "estimated"
                if air["aqi_kind"] == "cams"
                else ("measured" if air["aqi_kind"] else None),
                "aqi_hour": air["hour"],
                "temperature": wx["temperature"],
                "today_high": wx["today_high"],
                "today_low": wx["today_low"],
                "condition": wx["condition"],
            }
        )
    return out
