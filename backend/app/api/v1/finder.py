from datetime import date, datetime, timedelta
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.common import (
    EXTERNAL_TTL,
    SRC_CAMS,
    SRC_CPCB,
    SRC_WEATHER,
    Meta,
    cache,
    get_http,
    get_now,
    get_session,
    meta,
)
from app.services import finder
from app.services import route as routing

router = APIRouter(tags=["finder"])


class DayValue(BaseModel):
    date: date
    value: float


class Place(BaseModel):
    id: str
    name: str
    state: str | None
    lat: float
    lon: float
    kind: str  # station | town | hill_station
    distance_km: float
    approx_minutes: int
    value: float
    unit: str
    value_label: str  # measured | estimated
    value_source: str
    category: str | None
    category_key: str | None
    forecast: list[DayValue]
    forecast_label: str
    better_by: float | None  # how much better than where you are (AQI points or degrees)
    score: float


class Origin(BaseModel):
    name: str
    lat: float
    lon: float
    value: float | None


class FinderResult(Meta):
    goal: str
    mode: str
    radius_km: float | None
    origin: Origin
    places: list[Place]
    precautions: list[dict]
    empty_reason: str | None
    note: str


@router.get("/finder", response_model=FinderResult)
def find(
    goal: Literal["air", "heat"] = Query(description="air: cleaner air; heat: cooler place"),
    mode: Literal["nearby", "daytrip", "vacation"] = Query(
        description="nearby <= 10 km, daytrip <= 150 km, vacation: all India"
    ),
    from_: str = Query(
        alias="from",
        min_length=2,
        max_length=60,
        description="district id (e.g. delhi) or 'lat,lon'",
    ),
    session: Session = Depends(get_session),
    http: httpx.Client = Depends(get_http),
    now: datetime = Depends(get_now),
):
    """Cleaner or cooler places around you, ranked, each with its data label. Places without
    data are never returned."""
    try:
        origin = finder.resolve_origin(session, from_)
    except finder.FinderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    key = (
        "finder",
        goal,
        mode,
        round(origin.lat, 2),
        round(origin.lon, 2),
        now.replace(minute=0, second=0, microsecond=0),
    )
    try:
        if goal == "air":
            data = cache.get_or_set(
                key, EXTERNAL_TTL, lambda: finder.find_cleaner_air(session, http, origin, mode, now)
            )
            best = data["places"][0]["value"] if data["places"] else None
            precautions = finder.air_precautions(data["here_value"], best)
            source = f"{SRC_CPCB}; outlook: {SRC_CAMS}"
            label, empty = "mixed", None
            note = (
                "Current AQI is measured at CPCB stations (latest published hour); the 3-day "
                "outlook is a CAMS model estimate. Ranked by 60% today + 40% outlook."
            )
        else:
            data = cache.get_or_set(
                key, EXTERNAL_TTL, lambda: finder.find_cooler(session, http, origin, mode)
            )
            precautions = finder.heat_precautions(data.get("here_level"))
            source, label = SRC_WEATHER, "estimated"
            empty = data.get("empty_reason")
            note = (
                "Feels-like temperatures are Open-Meteo model forecasts (3-day mean of the daily "
                "maximum). Only places at least 1 °C cooler than here are shown."
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Forecast service unavailable") from exc
    if not data["places"] and empty is None:
        empty = "No place with data is cleaner or cooler than where you are in this range."
    return {
        "goal": goal,
        "mode": mode,
        "radius_km": finder.RADIUS[mode],
        "origin": {
            "name": origin.name,
            "lat": origin.lat,
            "lon": origin.lon,
            "value": data["here_value"],
        },
        "places": data["places"],
        "precautions": precautions,
        "empty_reason": empty,
        "note": note,
        **meta(source, now - timedelta(minutes=0), label, now),
    }


class Route(Meta):
    distance_km: float
    duration_min: int
    geometry: list[list[float]]  # [[lat, lon], ...]
    maps_url: str


@router.get("/route", response_model=Route)
def get_route(
    from_: str = Query(alias="from", description="lat,lon"),
    to: str = Query(description="lat,lon"),
    http: httpx.Client = Depends(get_http),
    now: datetime = Depends(get_now),
):
    """Driving route (distance, time, line) between two points; cached for a day."""
    try:
        a, b = routing.parse_point(from_), routing.parse_point(to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="from/to must be 'lat,lon'") from exc
    try:
        data = cache.get_or_set(("route", a, b), 24 * 3600, lambda: routing.route(http, a, b))
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="No route available right now") from exc
    maps = (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={a[0]},{a[1]}&destination={b[0]},{b[1]}&travelmode=driving"
    )
    return {
        **{k: v for k, v in data.items() if k != "source"},
        "maps_url": maps,
        **meta(data["source"], now, "estimated", now),
    }
