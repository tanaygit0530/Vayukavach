"""OpenAQ v3: Indian station history near each configured district.

- Finds locations inside a box around each district (bbox is lon/lat, GeoJSON order),
  then keeps those within RADIUS_KM.
- For every sensor we care about, fetches hourly values from the last stored hour (or
  90 days back) to now. Hours inside that window with no value become 'missing' rows.
- Respects OpenAQ's limits (60 requests/minute, 2,000/hour) with request spacing and a
  per-run budget; an unfinished backfill simply continues on the next run.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Reading, Station
from collectors.common import (
    BudgetExhausted,
    HttpClient,
    RunStats,
    concentration_status,
    floor_hour,
    haversine_km,
    hours_between,
    to_standard_unit,
    upsert,
    utc_now,
)
from collectors.districts import DistrictRow

BASE = "https://api.openaq.org/v3"
BACKFILL_DAYS = 90
RADIUS_KM = 25.0
BOX_DEG = 0.25
PAGE_LIMIT = 1000
INACTIVE_AFTER_DAYS = 7
REQUESTS_PER_MINUTE = 55  # under the 60/min limit
RUN_BUDGET = 1500  # under the 2,000/hour limit, leaves room for other callers

PARAMETERS = {"pm25": "pm25", "pm10": "pm10", "no2": "no2", "so2": "so2", "co": "co",
              "o3": "o3", "nh3": "nh3"}  # fmt: skip


def _parse_utc(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def find_locations(http: HttpClient, district: DistrictRow) -> list[dict]:
    bbox = ",".join(
        f"{v:.4f}"
        for v in (
            district.lon - BOX_DEG,
            district.lat - BOX_DEG,
            district.lon + BOX_DEG,
            district.lat + BOX_DEG,
        )
    )
    payload = http.get_json(f"{BASE}/locations", {"bbox": bbox, "limit": PAGE_LIMIT})
    out = []
    for loc in payload.get("results") or []:
        coords = loc.get("coordinates") or {}
        lat, lon = coords.get("latitude"), coords.get("longitude")
        if lat is None or lon is None:
            continue
        if (loc.get("country") or {}).get("code") not in (None, "IN"):
            continue
        if haversine_km(lat, lon, district.lat, district.lon) <= RADIUS_KM:
            out.append(loc)
    return out


def station_row(loc: dict, district: DistrictRow, now: datetime) -> dict:
    last = (loc.get("datetimeLast") or {}).get("utc")
    last_dt = _parse_utc(last) if last else None
    coords = loc["coordinates"]
    return {
        "source": "openaq",
        "external_id": str(loc["id"]),
        "name": loc.get("name") or str(loc["id"]),
        "city": loc.get("locality") or district.name,
        "state": None,
        "lat": coords["latitude"],
        "lon": coords["longitude"],
        "district_id": district.id,
        "is_active": bool(last_dt and last_dt >= now - timedelta(days=INACTIVE_AFTER_DAYS)),
        "last_seen_at": last_dt,
    }


def parse_hours(
    results: list[dict], station_id: int, pollutant: str, fetched_at: datetime
) -> list[dict]:
    rows = []
    for item in results:
        value = item.get("value")
        period = item.get("period") or {}
        start = ((period.get("datetimeFrom") or {}).get("utc")) or None
        if value is None or start is None or value < 0:
            continue
        unit_raw = (item.get("parameter") or {}).get("units") or "µg/m³"
        std_value, unit = to_standard_unit(pollutant, float(value), unit_raw)
        rows.append(
            {
                "station_id": station_id,
                "hour": floor_hour(_parse_utc(start)),
                "pollutant": pollutant,
                "value": std_value,
                "unit": unit,
                "status": concentration_status(pollutant, std_value, unit),
                "reason": None,
                "source": "openaq",
                "fetched_at": fetched_at,
            }
        )
    return rows


def missing_rows(
    have: set[datetime],
    start: datetime,
    end: datetime,
    station_id: int,
    pollutant: str,
    fetched_at: datetime,
) -> list[dict]:
    unit = "mg/m3" if pollutant == "co" else "ug/m3"
    return [
        {
            "station_id": station_id,
            "hour": h,
            "pollutant": pollutant,
            "value": None,
            "unit": unit,
            "status": "missing",
            "reason": "absent_in_openaq",
            "source": "openaq",
            "fetched_at": fetched_at,
        }
        for h in hours_between(start, end)
        if h not in have
    ]


def fetch_sensor_hours(
    http: HttpClient, sensor_id: int, start: datetime, end: datetime
) -> list[dict]:
    results: list[dict] = []
    page = 1
    while True:
        payload = http.get_json(
            f"{BASE}/sensors/{sensor_id}/hours",
            {
                "datetime_from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "datetime_to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": PAGE_LIMIT,
                "page": page,
            },
        )
        batch = payload.get("results") or []
        results.extend(batch)
        if len(batch) < PAGE_LIMIT:
            return results
        page += 1


def run(session: Session, http: HttpClient, districts: list[DistrictRow], stats: RunStats):
    api_key = get_settings().openaq_api_key
    if not api_key:
        stats.skipped = True
        stats.notes.append("OPENAQ_API_KEY not set")
        return
    http.client.headers["X-API-Key"] = api_key
    now = utc_now()
    end = floor_hour(now)
    sensors_done = sensors_left = 0
    try:
        for district in districts:
            for loc in find_locations(http, district):
                row = station_row(loc, district, now)
                upsert(session, Station.__table__, [row], ["source", "external_id"])
                station_id = session.execute(
                    select(Station.id).where(
                        Station.source == "openaq", Station.external_id == row["external_id"]
                    )
                ).scalar_one()
                if not row["is_active"]:
                    continue
                for sensor in loc.get("sensors") or []:
                    pollutant = PARAMETERS.get((sensor.get("parameter") or {}).get("name"))
                    if not pollutant:
                        continue
                    # Resume after the last real value (not after a 'missing' marker), so
                    # data that OpenAQ publishes late still fills earlier gaps.
                    last_ok = session.execute(
                        select(func.max(Reading.hour)).where(
                            Reading.station_id == station_id,
                            Reading.pollutant == pollutant,
                            Reading.status != "missing",
                        )
                    ).scalar()
                    if last_ok:
                        start = last_ok + timedelta(hours=1)
                    else:
                        start = end - timedelta(days=BACKFILL_DAYS)
                    first = (loc.get("datetimeFirst") or {}).get("utc")
                    if first:
                        start = max(start, floor_hour(_parse_utc(first)))
                    if start >= end:
                        continue
                    if http.rate_limit.exhausted:
                        sensors_left += 1
                        continue
                    results = fetch_sensor_hours(http, sensor["id"], start, end)
                    ok = parse_hours(results, station_id, pollutant, now)
                    ok = [r for r in ok if start <= r["hour"] < end]
                    gaps = missing_rows({r["hour"] for r in ok}, start, end, station_id,
                                        pollutant, now)  # fmt: skip
                    key = ["station_id", "hour", "pollutant"]
                    stats.rows += upsert(session, Reading.__table__, ok, key)
                    stats.rows += upsert(session, Reading.__table__, gaps, key, do_nothing=True)
                    session.commit()  # keep progress if a later request fails
                    sensors_done += 1
    except BudgetExhausted:
        sensors_left += 1
    stats.notes.append(f"{sensors_done} sensors updated, {http.rate_limit.calls} requests")
    if sensors_left:
        stats.notes.append("request budget reached; backfill continues next run")
