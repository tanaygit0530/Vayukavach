"""Open-Meteo collectors: CAMS air-quality model and weather forecast (no API key).

Both are requested with timezone=Asia/Kolkata (times come back in IST) and converted to
UTC with the response's utc_offset_seconds before storing. Data: Open-Meteo, CC BY 4.0;
air model: Copernicus Atmosphere Monitoring Service (CAMS).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import ModelAir, Weather, WeatherDaily
from collectors.common import HttpClient, RunStats, chunked, floor_hour, upsert, utc_now
from collectors.districts import DistrictRow

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "Asia/Kolkata"
LOCATIONS_PER_CALL = 50

AIR_VARIABLES = {
    "pm2_5": "pm25",
    "pm10": "pm10",
    "nitrogen_dioxide": "no2",
    "sulphur_dioxide": "so2",
    "carbon_monoxide": "co",
    "ozone": "o3",
    "ammonia": "nh3",
    "dust": "dust",
}

HOURLY_WEATHER = {
    "temperature_2m": "temperature",
    "apparent_temperature": "apparent_temperature",
    "relative_humidity_2m": "humidity",
    "dew_point_2m": "dew_point",
    "wind_speed_10m": "wind_speed",
    "wind_gusts_10m": "wind_gusts",
    "wind_direction_10m": "wind_direction",
    "pressure_msl": "pressure",
    "cloud_cover": "cloud_cover",
    "precipitation": "precipitation",
    "precipitation_probability": "precipitation_probability",
    "visibility": "visibility",
    "uv_index": "uv_index",
    "weather_code": "weather_code",
    "boundary_layer_height": "boundary_layer_height",
}

DAILY_WEATHER = {
    "weather_code": "weather_code",
    "temperature_2m_max": "temperature_max",
    "temperature_2m_min": "temperature_min",
    "apparent_temperature_max": "apparent_temperature_max",
    "apparent_temperature_min": "apparent_temperature_min",
    "sunrise": "sunrise",
    "sunset": "sunset",
    "daylight_duration": "daylight_duration",
    "uv_index_max": "uv_index_max",
    "precipitation_sum": "precipitation_sum",
    "precipitation_probability_max": "precipitation_probability_max",
}


def _local_to_utc(raw: str, offset_s: int) -> datetime:
    return (datetime.fromisoformat(raw) - timedelta(seconds=offset_s)).replace(tzinfo=UTC)


def _as_list(payload) -> list[dict]:
    return payload if isinstance(payload, list) else [payload]


def _coords(districts: Sequence[DistrictRow]) -> dict[str, str]:
    return {
        "latitude": ",".join(f"{d.lat:.4f}" for d in districts),
        "longitude": ",".join(f"{d.lon:.4f}" for d in districts),
    }


# ---------------------------------------------------------------- air (CAMS)


def parse_air(payload, districts: Sequence[DistrictRow], fetched_at: datetime) -> list[dict]:
    model_run = floor_hour(fetched_at)
    rows: list[dict] = []
    for loc, district in zip(_as_list(payload), districts, strict=True):
        offset = int(loc.get("utc_offset_seconds", 0))
        hourly = loc["hourly"]
        units = loc.get("hourly_units", {})
        for i, raw_time in enumerate(hourly["time"]):
            hour = _local_to_utc(raw_time, offset)
            for var, pollutant in AIR_VARIABLES.items():
                values = hourly.get(var)
                if values is None:
                    continue
                value = values[i]
                unit = "ug/m3"
                if value is not None and pollutant == "co":
                    # Open-Meteo gives CO in ug/m3; CPCB uses mg/m3.
                    value, unit = value / 1000.0, "mg/m3"
                elif pollutant == "co":
                    unit = "mg/m3"
                elif units.get(var) not in (None, "μg/m³", "µg/m³"):
                    raise ValueError(f"unexpected unit {units.get(var)!r} for {var}")
                rows.append(
                    {
                        "district_id": district.id,
                        "lat": round(float(loc["latitude"]), 4),
                        "lon": round(float(loc["longitude"]), 4),
                        "hour": hour,
                        "pollutant": pollutant,
                        "value": value,
                        "unit": unit,
                        "model_run": model_run,
                        "is_forecast": hour > fetched_at,
                        "fetched_at": fetched_at,
                    }
                )
    return rows


def run_air(session: Session, http: HttpClient, districts: list[DistrictRow], stats: RunStats):
    fetched_at = utc_now()
    for batch in chunked(districts, LOCATIONS_PER_CALL):
        payload = http.get_json(
            AIR_URL,
            {
                **_coords(batch),
                "hourly": ",".join(AIR_VARIABLES),
                "forecast_days": 5,
                "past_days": 1,
                "timezone": TIMEZONE,
            },
        )
        rows = parse_air(payload, batch, fetched_at)
        stats.rows += upsert(session, ModelAir.__table__, rows, ["lat", "lon", "hour", "pollutant"])
    stats.notes.append(f"{len(districts)} districts")


# ---------------------------------------------------------------- weather


def parse_weather(
    payload, districts: Sequence[DistrictRow], fetched_at: datetime
) -> tuple[list[dict], list[dict]]:
    hourly_rows: list[dict] = []
    daily_rows: list[dict] = []
    today_ist = (fetched_at + timedelta(hours=5, minutes=30)).date()
    for loc, district in zip(_as_list(payload), districts, strict=True):
        offset = int(loc.get("utc_offset_seconds", 0))
        hourly = loc["hourly"]
        for i, raw_time in enumerate(hourly["time"]):
            hour = _local_to_utc(raw_time, offset)
            row = {
                "district_id": district.id,
                "hour": hour,
                "is_forecast": hour > fetched_at,
                "fetched_at": fetched_at,
            }
            for var, col in HOURLY_WEATHER.items():
                values = hourly.get(var)
                row[col] = values[i] if values is not None else None
            hourly_rows.append(row)

        daily = loc.get("daily") or {}
        for i, raw_date in enumerate(daily.get("time", [])):
            day = date.fromisoformat(raw_date)
            row = {
                "district_id": district.id,
                "date": day,
                "is_forecast": day > today_ist,
                "fetched_at": fetched_at,
            }
            for var, col in DAILY_WEATHER.items():
                values = daily.get(var)
                value = values[i] if values is not None else None
                if col in {"sunrise", "sunset"} and value is not None:
                    value = _local_to_utc(value, offset)
                row[col] = value
            daily_rows.append(row)
    return hourly_rows, daily_rows


def run_weather(session: Session, http: HttpClient, districts: list[DistrictRow], stats: RunStats):
    fetched_at = utc_now()
    for batch in chunked(districts, LOCATIONS_PER_CALL):
        payload = http.get_json(
            WEATHER_URL,
            {
                **_coords(batch),
                "hourly": ",".join(HOURLY_WEATHER),
                "daily": ",".join(DAILY_WEATHER),
                "forecast_days": 16,
                "past_days": 1,
                "timezone": TIMEZONE,
            },
        )
        hourly_rows, daily_rows = parse_weather(payload, batch, fetched_at)
        stats.rows += upsert(session, Weather.__table__, hourly_rows, ["district_id", "hour"])
        stats.rows += upsert(session, WeatherDaily.__table__, daily_rows, ["district_id", "date"])
    stats.notes.append(f"{len(districts)} districts")
