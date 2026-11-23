"""Temperature- and Heat-tab queries from stored Open-Meteo data (model values: Estimated)."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import heat
from app.analysis.summary import floor_ist_hour
from app.analysis.time import IST, day_bounds, ist_date
from app.models import District, Weather, WeatherDaily
from app.services.reference import compass, condition, dispersion_note, uv_category

HOURLY_FIELDS = (
    "temperature", "apparent_temperature", "humidity", "dew_point", "wind_speed", "wind_gusts",
    "wind_direction", "pressure", "cloud_cover", "precipitation", "precipitation_probability",
    "visibility", "uv_index", "weather_code", "boundary_layer_height",
)  # fmt: skip


def _hourly(session: Session, district_id: int, start: datetime, end: datetime):
    return (
        session.execute(
            select(Weather)
            .where(Weather.district_id == district_id, Weather.hour >= start, Weather.hour < end)
            .order_by(Weather.hour)
        )
        .scalars()
        .all()
    )


def _daily(session: Session, district_id: int, first, days: int):
    return (
        session.execute(
            select(WeatherDaily)
            .where(
                WeatherDaily.district_id == district_id,
                WeatherDaily.date >= first,
                WeatherDaily.date < first + timedelta(days=days),
            )
            .order_by(WeatherDaily.date)
        )
        .scalars()
        .all()
    )


def current_row(session: Session, district: District, now: datetime) -> Weather | None:
    hour = floor_ist_hour(now)
    rows = _hourly(session, district.id, hour - timedelta(hours=3), hour + timedelta(hours=1))
    return rows[-1] if rows else None


def weather_now(session: Session, district: District, now: datetime) -> dict:
    row = current_row(session, district, now)
    today = _daily(session, district.id, ist_date(now), 1)
    d = today[0] if today else None
    base = {f: getattr(row, f) if row else None for f in HOURLY_FIELDS}
    return {
        **base,
        "hour": row.hour if row else None,
        "fetched_at": row.fetched_at if row else None,
        "condition": condition(base["weather_code"]),
        "wind_direction_compass": compass(base["wind_direction"]),
        "today_high": d.temperature_max if d else None,
        "today_low": d.temperature_min if d else None,
        "feels_like_reason": feels_like_reason(
            base["temperature"],
            base["apparent_temperature"],
            base["humidity"],
            base["wind_speed"],
        ),  # fmt: skip
    }


def feels_like_reason(temp, apparent, humidity, wind) -> str | None:
    """One-line reason why it feels warmer or cooler than the thermometer reading."""
    if temp is None or apparent is None:
        return None
    diff = apparent - temp
    if abs(diff) < 1:
        return "Feels about the same as the air temperature."
    if diff > 0:
        if humidity is not None and humidity >= 60:
            return "Humid air makes it feel warmer: sweat evaporates slowly."
        return "Strong sun and little wind make it feel warmer."
    if wind is not None and wind >= 10:
        return "Wind makes it feel cooler than the air temperature."
    return "Dry air makes it feel cooler than the air temperature."


def weather_hourly(session: Session, district: District, now: datetime) -> list[dict]:
    """Today 00:00 IST to tomorrow 23:00 IST."""
    start = day_bounds(ist_date(now))[0]
    rows = _hourly(session, district.id, start, start + timedelta(hours=48))
    return [
        {
            "hour": r.hour,
            **{f: getattr(r, f) for f in HOURLY_FIELDS},
            "condition": condition(r.weather_code),
            "is_forecast": r.is_forecast,
        }
        for r in rows
    ]


def weather_daily(session: Session, district: District, now: datetime) -> list[dict]:
    return [
        {
            "date": d.date,
            "temperature_min": d.temperature_min,
            "temperature_max": d.temperature_max,
            "apparent_temperature_max": d.apparent_temperature_max,
            "weather_code": d.weather_code,
            "condition": condition(d.weather_code),
            "precipitation_sum": d.precipitation_sum,
            "precipitation_probability_max": d.precipitation_probability_max,
            "uv_index_max": d.uv_index_max,
            "is_forecast": d.is_forecast,
        }
        for d in _daily(session, district.id, ist_date(now), 10)
    ]


def weather_sun(session: Session, district: District, now: datetime) -> list[dict]:
    return [
        {
            "date": d.date,
            "sunrise": d.sunrise,
            "sunset": d.sunset,
            "daylight_seconds": d.daylight_duration,
        }  # fmt: skip
        for d in _daily(session, district.id, ist_date(now), 2)
    ]


def weather_uv(session: Session, district: District, now: datetime) -> dict:
    row = current_row(session, district, now)
    start, end = day_bounds(ist_date(now))
    hours = _hourly(session, district.id, start, end)
    cover = [h for h in hours if h.uv_index is not None and h.uv_index >= 3]
    today = _daily(session, district.id, ist_date(now), 1)
    uv_max = today[0].uv_index_max if today else None
    return {
        "uv_index": row.uv_index if row else None,
        "category": uv_category(row.uv_index if row else None),
        "uv_index_max": uv_max,
        "max_category": uv_category(uv_max),
        "cover_up_from": cover[0].hour if cover else None,
        "cover_up_until": cover[-1].hour + timedelta(hours=1) if cover else None,
        "hour": row.hour if row else None,
        "fetched_at": row.fetched_at if row else None,
    }


def wind(session: Session, district: District, now: datetime) -> dict:
    row = current_row(session, district, now)
    return {
        "speed_kmh": row.wind_speed if row else None,
        "gusts_kmh": row.wind_gusts if row else None,
        "direction_deg": row.wind_direction if row else None,
        "direction_compass": compass(row.wind_direction) if row else None,
        "boundary_layer_m": row.boundary_layer_height if row else None,
        "note": dispersion_note(row.wind_speed, row.boundary_layer_height) if row else None,
        "hour": row.hour if row else None,
        "fetched_at": row.fetched_at if row else None,
    }


# ---------------------------------------------------------------- heat


def _assess(rows) -> list[heat.HeatHour]:
    return [
        heat.assess_hour(
            r.hour, r.hour.astimezone(IST).hour, r.temperature, r.humidity, r.apparent_temperature
        )  # fmt: skip
        for r in rows
    ]


def heat_report(session: Session, district: District, now: datetime) -> dict:
    today = ist_date(now)
    start, end = day_bounds(today)
    today_hours = _assess(_hourly(session, district.id, start, end))
    current = floor_ist_hour(now)
    now_hour = next((h for h in today_hours if h.hour == current), None)
    if now_hour is None and today_hours:
        past = [h for h in today_hours if h.hour <= current]
        now_hour = past[-1] if past else today_hours[0]
    level = now_hour.level if now_hour else None
    worst = heat.worst_level(today_hours)
    daily = []
    rows10 = _hourly(session, district.id, start, start + timedelta(days=10))
    by_day: dict = {}
    for h in _assess(rows10):
        by_day.setdefault(ist_date(h.hour), []).append(h)
    for day in sorted(by_day):
        hs = [h for h in by_day[day] if h.heat_index is not None]
        if not hs:
            continue
        temps = [h.temperature for h in hs]
        daily.append(
            {
                "date": day,
                "temperature_min": min(temps),
                "temperature_max": max(temps),
                "heat_index_max": max(h.heat_index for h in hs),
                "wet_bulb_max": max(h.wet_bulb for h in hs),
                "level": heat.worst_level(hs),
                "is_forecast": day > today,
            }
        )
    fetched = _hourly(session, district.id, current, current + timedelta(hours=1))
    return {
        "hour": now_hour.hour if now_hour else None,
        "fetched_at": fetched[0].fetched_at if fetched else None,
        "temperature": now_hour.temperature if now_hour else None,
        "humidity": now_hour.humidity if now_hour else None,
        "feels_like": now_hour.apparent_temperature if now_hour else None,
        "heat_index": now_hour.heat_index if now_hour else None,
        "wet_bulb": now_hour.wet_bulb if now_hour else None,
        "level": level,
        "level_name": heat.LEVEL_NAMES.get(level) if level else None,
        "instruction": heat.WORK_REST.get(level) if level else None,
        "worst_level_today": worst,
        "safe_work_windows": [
            {"from_hour": a, "to_hour": b} for a, b in heat.safe_windows(today_hours)
        ],
        "hourly": [
            {
                "hour": h.hour,
                "local_hour": h.local_hour,
                "temperature": h.temperature,
                "feels_like": h.apparent_temperature,
                "heat_index": h.heat_index,
                "wet_bulb": h.wet_bulb,
                "level": h.level,
            }  # fmt: skip
            for h in today_hours
        ],
        "daily": daily,
        "tips": heat.tips_for(worst) if worst else [],
        "tips_source": heat.TIPS_SOURCE,
        "thresholds_status": heat.THRESHOLDS_STATUS,
    }
