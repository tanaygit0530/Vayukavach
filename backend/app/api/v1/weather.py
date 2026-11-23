from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.common import (
    SRC_WEATHER,
    Meta,
    get_district,
    get_now,
    get_session,
    meta,
    to_ist,
)
from app.models import District
from app.services import weather as wx

router = APIRouter(prefix="/weather", tags=["weather"])
NOTE = "Model values from Open-Meteo: earlier hours are model analysis, later hours forecast."


class WeatherFields(BaseModel):
    temperature: float | None
    apparent_temperature: float | None
    humidity: float | None
    dew_point: float | None
    wind_speed: float | None
    wind_gusts: float | None
    wind_direction: float | None
    pressure: float | None
    cloud_cover: float | None
    precipitation: float | None
    precipitation_probability: float | None
    visibility: float | None
    uv_index: float | None
    weather_code: int | None
    boundary_layer_height: float | None
    condition: str | None


class WeatherNow(Meta, WeatherFields):
    district: str
    hour: datetime | None
    today_high: float | None
    today_low: float | None
    wind_direction_compass: str | None
    feels_like_reason: str | None
    note: str


@router.get("/{district}/now", response_model=WeatherNow)
def now_(
    district: District = Depends(get_district),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """Current conditions, feels-like with a reason, today's high and low."""
    data = wx.weather_now(session, district, now)
    return {
        **data,
        "district": district.slug,
        "hour": to_ist(data["hour"]),
        "note": NOTE,
        **meta(SRC_WEATHER, data["fetched_at"], "estimated", now),
    }


class WeatherHour(WeatherFields):
    hour: datetime
    is_forecast: bool


class WeatherHourly(Meta):
    district: str
    hours: list[WeatherHour]
    note: str


@router.get("/{district}/hourly", response_model=WeatherHourly)
def hourly(
    district: District = Depends(get_district),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """48 hours: today 00:00 IST to tomorrow 23:00 IST."""
    hours = wx.weather_hourly(session, district, now)
    current = wx.current_row(session, district, now)
    return {
        "district": district.slug,
        "hours": [{**h, "hour": to_ist(h["hour"])} for h in hours],
        "note": NOTE,
        **meta(SRC_WEATHER, current.fetched_at if current else None, "estimated", now),
    }


class WeatherDay(BaseModel):
    date: date
    temperature_min: float | None
    temperature_max: float | None
    apparent_temperature_max: float | None
    weather_code: int | None
    condition: str | None
    precipitation_sum: float | None
    precipitation_probability_max: float | None
    uv_index_max: float | None
    is_forecast: bool


class WeatherDaily(Meta):
    district: str
    days: list[WeatherDay]


@router.get("/{district}/daily", response_model=WeatherDaily)
def daily(
    district: District = Depends(get_district),
    days: int = Query(default=10, ge=1, le=16, description="Days from today (max 16)"),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """Daily forecast from today: low, high, sky condition, rain, UV (default 10 days)."""
    current = wx.current_row(session, district, now)
    return {
        "district": district.slug,
        "days": wx.weather_daily(session, district, now, days),
        **meta(SRC_WEATHER, current.fetched_at if current else None, "estimated", now),
    }


class SunDay(BaseModel):
    date: date
    sunrise: datetime | None
    sunset: datetime | None
    daylight_seconds: float | None


class Sun(Meta):
    district: str
    days: list[SunDay]


@router.get("/{district}/sun", response_model=Sun)
def sun(
    district: District = Depends(get_district),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """Sunrise, sunset and daylight for today and tomorrow (IST)."""
    days = wx.weather_sun(session, district, now)
    current = wx.current_row(session, district, now)
    return {
        "district": district.slug,
        "days": [
            {**d, "sunrise": to_ist(d["sunrise"]), "sunset": to_ist(d["sunset"])} for d in days
        ],  # fmt: skip
        **meta(SRC_WEATHER, current.fetched_at if current else None, "estimated", now),
    }


class Uv(Meta):
    district: str
    uv_index: float | None
    category: str | None
    uv_index_max: float | None
    max_category: str | None
    cover_up_from: datetime | None
    cover_up_until: datetime | None


@router.get("/{district}/uv", response_model=Uv)
def uv(
    district: District = Depends(get_district),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """UV index now and today's max (WHO categories), and the hours to cover up (UV >= 3)."""
    data = wx.weather_uv(session, district, now)
    return {
        **{k: v for k, v in data.items() if k not in ("hour", "fetched_at")},
        "district": district.slug,
        "cover_up_from": to_ist(data["cover_up_from"]),
        "cover_up_until": to_ist(data["cover_up_until"]),
        **meta(SRC_WEATHER, data["fetched_at"], "estimated", now),
    }
