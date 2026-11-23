"""History for forecasting: daily city AQI (target) and daily CAMS + weather (features).

- OpenAQ /sensors/{id}/days gives daily means with observed-hour counts for each live sensor
  of the reference monitors (one request per sensor). Backfilled once; recent days are then
  derived nightly from stored hourly readings (same definition).
- Features per IST day: CAMS pollutants (Open-Meteo air-quality API, history and the 5-day
  forecast) and weather (Open-Meteo archive for history, forecast API for recent and the next
  15 days), aggregated from hourly values.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.forecast.daily_aqi import POLLUTANTS, city_daily, station_days_from_hourly
from app.models import CityDailyAqi, DistrictDailyFeatures, Station
from collectors.common import (
    BudgetExhausted,
    HttpClient,
    HTTPFailure,
    RunStats,
    chunked,
    to_standard_unit,
    utc_now,
)
from collectors.districts import DistrictRow
from collectors.openaq import BASE, PAGE_LIMIT, live_sensors

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
IST = timedelta(hours=5, minutes=30)
HISTORY_START = date(2025, 1, 1)

CAMS_VARS = {
    "pm2_5": "cams_pm25",
    "pm10": "cams_pm10",
    "nitrogen_dioxide": "cams_no2",
    "sulphur_dioxide": "cams_so2",
    "carbon_monoxide": "cams_co",
    "ozone": "cams_o3",
}
WX_VARS = ("temperature_2m", "relative_humidity_2m", "wind_speed_10m", "precipitation",
           "boundary_layer_height")  # fmt: skip


def today_ist(now: datetime | None = None) -> date:
    return ((now or utc_now()) + IST).date()


# ---------------------------------------------------------------- target: daily city AQI


def parse_days(results: list[dict], pollutant: str, unit: str | None, cpcb_native: bool):
    rows = []
    for item in results:
        value = item.get("value")
        local = ((item.get("period") or {}).get("datetimeFrom") or {}).get("local")
        observed = (item.get("coverage") or {}).get("observedCount")
        if value is None or local is None or value < 0:
            continue
        raw_unit = unit or (item.get("parameter") or {}).get("units") or "µg/m³"
        if cpcb_native and raw_unit.strip().lower() in {"ppb", "ppm"}:
            std = float(value)
        else:
            std, _ = to_standard_unit(pollutant, float(value), raw_unit)
        rows.append((date.fromisoformat(local[:10]), pollutant, std, int(observed or 0)))
    return rows


def upsert_city_daily(session: Session, district_id: int, frame: pd.DataFrame, source: str) -> int:
    if frame.empty:
        return 0
    now = datetime.now(UTC)
    rows = [
        {
            "district_id": district_id,
            "date": r.date,
            "aqi": None if pd.isna(r.aqi) else int(r.aqi),
            "stations": int(r.stations),
            **{p: None if pd.isna(getattr(r, p)) else float(getattr(r, p)) for p in POLLUTANTS},
            "source": source,
            "computed_at": now,
        }
        for r in frame.itertuples()
    ]
    for chunk in chunked(rows, 500):
        stmt = insert(CityDailyAqi).values(list(chunk))
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["district_id", "date"],
                set_={k: stmt.excluded[k] for k in chunk[0] if k not in ("district_id", "date")},
            )
        )
    return len(rows)


def backfill_daily_aqi(session: Session, http: HttpClient, districts: list[DistrictRow],
                       stats: RunStats, start: date = HISTORY_START) -> None:  # fmt: skip
    """One request per live sensor of each district's reference monitors."""
    key = {"X-API-Key": get_settings().openaq_api_key}  # sent to OpenAQ only
    now = utc_now()
    for district in districts:
        stations = (
            session.execute(
                select(Station).where(
                    Station.district_id == district.id,
                    Station.source == "openaq",
                    Station.is_reference,
                    Station.is_active,
                )
            )
            .scalars()
            .all()
        )
        records = []
        for station in stations:
            for sensor in live_sensors(session, station.id, now):
                if sensor.pollutant not in POLLUTANTS:
                    continue
                cpcb_native = station.is_reference and (sensor.unit or "").lower() in {"ppb", "ppm"}
                page = 1
                try:
                    while True:
                        payload = http.get_json(
                            f"{BASE}/sensors/{sensor.external_id}/days",
                            {"limit": PAGE_LIMIT, "page": page},
                            headers=key,
                        )
                        batch = payload.get("results") or []
                        for d, pol, value, observed in parse_days(
                            batch, sensor.pollutant, sensor.unit, cpcb_native
                        ):
                            if d >= start:
                                records.append((station.id, d, pol, value, observed))
                        if len(batch) < PAGE_LIMIT:
                            break
                        page += 1
                except HTTPFailure as exc:
                    stats.errors += 1
                    stats.notes.append(f"sensor {sensor.external_id}: {exc}")
        frame = pd.DataFrame(
            records, columns=["station_id", "date", "pollutant", "value", "observed_hours"]
        )
        n = upsert_city_daily(session, district.id, city_daily(frame), "openaq_daily")
        session.commit()
        stats.rows += n
        stats.notes.append(f"{district.slug}: {n} days")


def daily_aqi_from_readings(session: Session, districts: list[DistrictRow], stats: RunStats,
                            days: int = 4) -> None:  # fmt: skip
    """Recent days from stored hourly readings (same definition as the backfill)."""
    end_day = today_ist()  # today is partial: only complete days
    start_day = end_day - timedelta(days=days)
    start = datetime.combine(start_day, datetime.min.time(), tzinfo=UTC) - IST
    end = datetime.combine(end_day, datetime.min.time(), tzinfo=UTC) - IST
    for district in districts:
        rows = session.execute(
            text(
                "SELECT r.station_id, r.hour, r.pollutant, r.status, r.value FROM readings r"
                " JOIN stations s ON s.id = r.station_id WHERE s.district_id = :d"
                " AND s.source = 'openaq' AND s.is_reference AND r.hour >= :s AND r.hour < :e"
            ),
            {"d": district.id, "s": start, "e": end},
        ).all()
        df = pd.DataFrame(rows, columns=["station_id", "hour", "pollutant", "status", "value"])
        if df.empty:
            continue
        df["hour"] = pd.to_datetime(df["hour"], utc=True)
        stats.rows += upsert_city_daily(
            session, district.id, city_daily(station_days_from_hourly(df)), "readings"
        )
    session.commit()


# ---------------------------------------------------------------- features


def _daily_means(payload, districts: list[DistrictRow], names: dict[str, str]) -> pd.DataFrame:
    frames = []
    for loc, district in zip(payload if isinstance(payload, list) else [payload], districts,
                             strict=True):  # fmt: skip
        hourly = loc.get("hourly") or {}
        if not hourly.get("time"):
            continue
        df = pd.DataFrame({k: hourly.get(k) for k in names}, index=pd.to_datetime(hourly["time"]))
        df = df.apply(pd.to_numeric, errors="coerce")
        agg = {k: ("sum" if k == "precipitation" else "mean") for k in names}
        daily = df.groupby(df.index.date).agg(agg).rename(columns=names)
        daily["district_id"] = district.id
        frames.append(daily)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames)
    out.index.name = "date"
    return out.reset_index()


WX_NAMES = {"temperature_2m": "temperature_mean", "relative_humidity_2m": "humidity_mean",
            "wind_speed_10m": "wind_mean", "precipitation": "precipitation_sum",
            "boundary_layer_height": "blh_mean"}  # fmt: skip


def refresh_features(session: Session, http: HttpClient, districts: list[DistrictRow],
                     stats: RunStats, start: date | None = None) -> None:  # fmt: skip
    """CAMS + weather daily features from `start` (default: last 10 days) to +15 days."""
    today = today_ist()
    start = start or today - timedelta(days=10)
    fetched = utc_now()
    for batch in chunked(districts, 10):
        coords = {
            "latitude": ",".join(f"{d.lat:.4f}" for d in batch),
            "longitude": ",".join(f"{d.lon:.4f}" for d in batch),
            "timezone": "Asia/Kolkata",
        }
        cams = http.get_json(
            AIR_URL,
            {**coords, "hourly": ",".join(CAMS_VARS), "start_date": start.isoformat(),
             "end_date": (today + timedelta(days=4)).isoformat()},
        )  # fmt: skip
        cams_df = _daily_means(cams, batch, CAMS_VARS)
        if not cams_df.empty:
            cams_df["cams_co"] = cams_df["cams_co"] / 1000.0  # ug/m3 -> mg/m3
        parts = []
        archive_end = today - timedelta(days=6)
        if start <= archive_end:
            parts.append(
                _daily_means(
                    http.get_json(ARCHIVE_URL, {**coords, "hourly": ",".join(WX_VARS),
                                  "start_date": start.isoformat(),
                                  "end_date": archive_end.isoformat()}),
                    batch, WX_NAMES,
                )
            )  # fmt: skip
        parts.append(
            _daily_means(
                http.get_json(FORECAST_URL, {**coords, "hourly": ",".join(WX_VARS),
                              "past_days": 10, "forecast_days": 16}),
                batch, WX_NAMES,
            )
        )  # fmt: skip
        wx = pd.concat([p for p in parts if not p.empty])
        wx = wx.drop_duplicates(["district_id", "date"], keep="last")  # forecast API wins
        merged = wx.merge(cams_df, on=["district_id", "date"], how="outer")
        merged = merged[merged["date"] >= start]
        rows = []
        for r in merged.to_dict("records"):
            row = {k: (None if pd.isna(v) else v) for k, v in r.items()}
            row["district_id"] = int(row["district_id"])
            row["is_forecast"] = row["date"] > today
            row["fetched_at"] = fetched
            rows.append(row)
        for chunk in chunked(rows, 500):
            cols = set().union(*chunk)
            chunk = [{c: r.get(c) for c in cols} for r in chunk]
            stmt = insert(DistrictDailyFeatures).values(chunk)
            session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["district_id", "date"],
                    set_={k: stmt.excluded[k] for k in cols if k not in ("district_id", "date")},
                )
            )
        stats.rows += len(rows)
    session.commit()


def run_backfill(session: Session, http: HttpClient, districts: list[DistrictRow],
                 stats: RunStats) -> None:  # fmt: skip
    """One-off: ~2 years of features and daily AQI history."""
    refresh_features(session, http, districts, stats, start=HISTORY_START)
    try:
        backfill_daily_aqi(session, http, districts, stats)
    except BudgetExhausted:
        stats.notes.append("request budget reached; re-run to continue the AQI backfill")
