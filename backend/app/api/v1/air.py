from datetime import date, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.analysis.time import IST
from app.api.common import (
    DB_TTL,
    EXTERNAL_TTL,
    SRC_CAMS,
    SRC_CPCB,
    SRC_OPENAQ,
    SRC_WEATHER,
    Meta,
    cache,
    get_district,
    get_http,
    get_now,
    get_session,
    meta,
    to_ist,
)
from app.models import District
from app.services import air, airmap
from app.services import weather as wx
from app.services.reference import CPCB_HEALTH, CPCB_HEALTH_SOURCE

router = APIRouter(prefix="/air", tags=["air"])

KIND_SOURCE = {"official": SRC_CPCB, "measured": SRC_OPENAQ, "cams": SRC_CAMS}
KIND_LABEL = {"official": "measured", "measured": "measured", "cams": "estimated"}


def _cached(name: str, district: District, now: datetime, fn):
    key = (name, district.id, now.replace(minute=0, second=0, microsecond=0))
    return cache.get_or_set(key, DB_TTL, fn)


class AirNow(Meta):
    district: str
    aqi: int | None
    category: str | None
    category_key: str | None
    main_pollutant: str | None
    aqi_kind: str | None  # official (CPCB) | measured (our AQI from stations) | cams (model)
    hour: datetime | None
    stations_reporting: int | None
    visibility_m: float | None
    visibility_label: str = "estimated"
    completeness_pct: float | None
    shadow_aqi: int | None
    shadow_aqi_low: int | None
    shadow_aqi_high: int | None
    shadow_hour: datetime | None
    shadow_label: str = "estimated"


@router.get("/{district}/now", response_model=AirNow)
def now_(
    district: District = Depends(get_district),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """Current AQI (CPCB official if available), data completeness and shadow AQI."""
    data = _cached("air_now", district, now, lambda: air.air_now(session, district, now))
    vis = wx.current_row(session, district, now)
    kind = data["aqi_kind"]
    updated = data["hour"] + timedelta(hours=1) if data["hour"] else None
    return {
        **data,
        "district": district.slug,
        "hour": to_ist(data["hour"]),
        "shadow_hour": to_ist(data["shadow_hour"]),
        "visibility_m": vis.visibility if vis else None,
        **meta(KIND_SOURCE.get(kind, SRC_CPCB), updated, KIND_LABEL.get(kind), now),
    }


class HourPoint(BaseModel):
    hour: datetime
    official_aqi: int | None
    shadow_aqi: int | None
    shadow_aqi_low: int | None
    shadow_aqi_high: int | None
    estimated_aqi: int | None  # CAMS model, shown only when there is no official value
    forecast_aqi: int | None
    is_forecast: bool
    official_missing: bool


class AirHourly(Meta):
    district: str
    hours: list[HourPoint]


@router.get("/{district}/hourly", response_model=AirHourly)
def hourly(
    district: District = Depends(get_district),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """Today's 24 IST hours: CPCB official, shadow estimate (past) and CAMS forecast (future)."""
    hours = _cached("air_hourly", district, now, lambda: air.air_hourly(session, district, now))
    # freshest past value of any kind: official, then shadow, then model estimate
    past = [
        h["hour"]
        for h in hours
        if not h["is_forecast"]
        and (h["official_aqi"] or h["shadow_aqi"] or h["estimated_aqi"]) is not None
    ]
    updated = past[-1] + timedelta(hours=1) if past else None
    return {
        "district": district.slug,
        "hours": [{**h, "hour": to_ist(h["hour"])} for h in hours],
        **meta(f"{SRC_CPCB}; shadow: {SRC_OPENAQ}; forecast: {SRC_CAMS}", updated, "mixed", now),
    }


class DayRange(BaseModel):
    date: date
    low: int | None
    high: int | None
    median: int | None
    is_outlook: bool
    available: bool
    label: str
    method: str | None  # cams_corrected | cams_raw | outlook
    model_version: str | None


class AirDaily(Meta):
    district: str
    days: list[DayRange]
    note: str


@router.get("/{district}/daily", response_model=AirDaily)
def daily(
    district: District = Depends(get_district),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """10 days of AQI low-high. Days 1-5: CAMS forecast. Days 6-10: outlook (Phase 8)."""
    days = _cached("air_daily", district, now, lambda: air.air_daily(session, district, now))
    methods = {d["method"] for d in days if d["method"]}
    early = (
        "Days 1-5: CAMS forecast bias-corrected against stored station data"
        if "cams_corrected" in methods
        else "Days 1-5: raw CAMS forecast"
    )
    late = (
        "days 6-10: outlook model (median and 5-95% quantile range, lower confidence)"
        if "outlook" in methods
        else "days 6-10: not available (the outlook model is missing or not better than "
        "simple baselines)"
    )
    return {
        "district": district.slug,
        "days": days,
        "note": f"{early}; {late}. All Estimated.",
        **meta(f"{SRC_CAMS}; VayuKavach forecast models", now, "estimated", now),
    }


class Month(BaseModel):
    month: str
    avg_aqi: int | None
    days: int
    is_current: bool


class AirMonthly(Meta):
    district: str
    months: list[Month]


@router.get("/{district}/monthly", response_model=AirMonthly)
def monthly(
    district: District = Depends(get_district),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """Last 12 months: average daily AQI from stored data (no data -> null, never 0)."""
    months = _cached("air_monthly", district, now, lambda: air.air_monthly(session, district, now))
    return {
        "district": district.slug,
        "months": months,
        **meta(f"{SRC_OPENAQ}; {SRC_CPCB}", now, "measured", now),
    }


class PollutantValue(BaseModel):
    pollutant: str
    value: float | None
    unit: str
    sub_index: int | None
    label: str | None
    stations: int


class Co2(BaseModel):
    value: float
    unit: str
    hour: datetime
    label: str
    note: str


class AirPollutants(Meta):
    district: str
    pollutants: list[PollutantValue]
    co2: Co2 | None


@router.get("/{district}/pollutants", response_model=AirPollutants)
def pollutants(
    district: District = Depends(get_district),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """24-h values (8-h for CO and O3) and sub-indices; stations first, else CAMS model."""
    data = _cached("air_pol", district, now, lambda: air.air_pollutants(session, district, now))
    labels = {p["label"] for p in data["pollutants"] if p["label"]}
    label = labels.pop() if len(labels) == 1 else ("mixed" if labels else None)
    co2 = data["co2"]
    if co2:
        co2 = {**co2, "hour": to_ist(co2["hour"])}
    return {
        "district": district.slug,
        "pollutants": data["pollutants"],
        "co2": co2,
        **meta(f"{SRC_OPENAQ}; {SRC_CAMS}", data["window_end"], label, now),
    }


class StationPin(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    aqi: int | None
    category: str | None
    category_key: str | None
    main_pollutant: str | None
    status: str  # measured | estimated | silent
    last_seen_at: datetime | None


class AirStations(Meta):
    district: str
    stations: list[StationPin]


@router.get("/{district}/stations", response_model=AirStations)
def stations(
    district: District = Depends(get_district),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """Station pins: measured (reported), estimated (silent, filled from neighbours) or silent."""
    data = _cached("air_st", district, now, lambda: air.air_stations(session, district, now))
    hour = data["hour"]
    pins = [{**p, "last_seen_at": to_ist(p.get("last_seen_at"))} for p in data["stations"]]
    return {
        "district": district.slug,
        "stations": pins,
        **meta(SRC_CPCB, hour + timedelta(hours=1) if hour else None, "mixed", now),
    }


class Wind(Meta):
    district: str
    speed_kmh: float | None
    gusts_kmh: float | None
    direction_deg: float | None
    direction_compass: str | None
    boundary_layer_m: float | None
    note: str | None


@router.get("/{district}/wind", response_model=Wind)
def wind(
    district: District = Depends(get_district),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """Wind speed, gusts, direction and whether air is clearing or trapping pollution."""
    data = wx.wind(session, district, now)
    return {
        "district": district.slug,
        **{k: v for k, v in data.items() if k not in ("hour", "fetched_at")},
        **meta(SRC_WEATHER, data["fetched_at"], "estimated", now),
    }


class Advice(Meta):
    district: str
    aqi: int | None
    category: str | None
    category_key: str | None
    health_impact: str | None
    advice_source: str


@router.get("/{district}/advice", response_model=Advice)
def advice(
    district: District = Depends(get_district),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """CPCB's official health-impact statement for the current AQI category."""
    data = _cached("air_now", district, now, lambda: air.air_now(session, district, now))
    kind = data["aqi_kind"]
    return {
        "district": district.slug,
        "aqi": data["aqi"],
        "category": data["category"],
        "category_key": data["category_key"],
        "health_impact": CPCB_HEALTH.get(data["category_key"]) if data["category_key"] else None,
        "advice_source": CPCB_HEALTH_SOURCE,
        **meta(
            KIND_SOURCE.get(kind, SRC_CPCB),
            data["hour"] + timedelta(hours=1) if data["hour"] else None,
            KIND_LABEL.get(kind),
            now,
        ),  # fmt: skip
    }


class MapCell(BaseModel):
    lat: float
    lon: float
    pm25: float | None
    pm25_sub_index: int | None
    category_key: str | None


class AirMap(Meta):
    bbox: list[float]
    grid: int
    cells: list[MapCell]


@router.get("/map", response_model=AirMap)
def air_map(
    bbox: str = Query(description="minLon,minLat,maxLon,maxLat"),
    http: httpx.Client = Depends(get_http),
    now: datetime = Depends(get_now),
):
    """PM2.5 model grid for the map layer (CAMS, Estimated; cached 1 h)."""
    try:
        box = airmap.parse_bbox(bbox)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        data = cache.get_or_set(("map", box), EXTERNAL_TTL, lambda: airmap.fetch_grid(http, box))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Map data is unavailable") from exc
    updated = None
    if data["time_ist"]:
        updated = datetime.fromisoformat(data["time_ist"]).replace(tzinfo=IST)
    return {"bbox": list(box), "grid": data["grid"], "cells": data["cells"],
            **meta(SRC_CAMS, updated, "estimated", now)}  # fmt: skip
