from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.common import (
    DB_TTL,
    GEOCODE_TTL,
    SRC_CAMS,
    SRC_CPCB,
    SRC_GEOCODING,
    SRC_WEATHER,
    Meta,
    cache,
    get_http,
    get_now,
    get_session,
    meta,
    to_ist,
)
from app.services import places

router = APIRouter(prefix="/places", tags=["places"])


class Place(BaseModel):
    name: str | None
    state: str | None
    district: str | None
    lat: float
    lon: float
    population: int | None
    covered_district: str | None  # VayuKavach district within 50 km, if any
    distance_km: float | None


class PlaceSearch(Meta):
    results: list[Place]


@router.get("/search", response_model=PlaceSearch)
def search(
    q: str = Query(min_length=2, max_length=80),
    http: httpx.Client = Depends(get_http),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """Find Indian places by name (Open-Meteo Geocoding, cached 24 h)."""
    key = ("geocode", q.strip().lower())
    try:
        results = cache.get_or_set(key, GEOCODE_TTL, lambda: places.search(http, session, q))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Place search is unavailable") from exc
    return {"results": results, **meta(SRC_GEOCODING, now, None, now)}


class PlaceSummaryItem(BaseModel):
    id: str
    name: str
    state: str
    aqi: int | None
    category: str | None
    category_key: str | None
    aqi_label: str | None
    aqi_hour: datetime | None
    temperature: float | None
    today_high: float | None
    today_low: float | None
    condition: str | None


class PlaceSummary(Meta):
    places: list[PlaceSummaryItem]


@router.get("/summary", response_model=PlaceSummary)
def summary(
    ids: str = Query(description="Comma-separated district ids, e.g. delhi,mumbai"),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """AQI, temperature and today's high/low for saved places."""
    slugs = [s.strip().lower() for s in ids.split(",") if s.strip()][:20]
    items = cache.get_or_set(
        ("summary", tuple(slugs), now.replace(minute=0, second=0, microsecond=0)),
        DB_TTL,
        lambda: places.summary(session, slugs, now),
    )
    for item in items:
        item["aqi_hour"] = to_ist(item["aqi_hour"])
    hours = [i["aqi_hour"] for i in items if i["aqi_hour"]]
    label = (
        "mixed"
        if len({i["aqi_label"] for i in items if i["aqi_label"]}) > 1
        else (items[0]["aqi_label"] if items else None)
    )
    return {
        "places": items,
        **meta(
            f"{SRC_CPCB}; {SRC_CAMS}; {SRC_WEATHER}", min(hours) if hours else None, label, now
        ),  # fmt: skip
    }
