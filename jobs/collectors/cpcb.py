"""CPCB real-time air quality via data.gov.in.

The feed is a snapshot: one row per station and pollutant with `last_update` (IST) and
min / max / avg values. Observed in recorded responses (Nov 2026): the values are
**AQI sub-indices**, not concentrations (e.g. CO avg 63 is impossible in mg/m3), so they
are stored with unit 'aqi_subindex'. The API's offset paging is not stable (records repeat
across pages), so we request large pages and de-duplicate.

After every pull, each active CPCB station gets a row for the snapshot hour for every
pollutant it normally reports. If nothing arrived, that row is value NULL, status 'missing'.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Reading, Station
from collectors.common import (
    IST_OFFSET,
    HttpClient,
    RunStats,
    floor_hour,
    upsert,
    utc_now,
)
from collectors.districts import DistrictRow, nearest_district

RESOURCE_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
PAGE_SIZE = 1000
UNIT = "aqi_subindex"
INACTIVE_AFTER_DAYS = 7

POLLUTANT_MAP = {
    "PM2.5": "pm25",
    "PM10": "pm10",
    "NO2": "no2",
    "SO2": "so2",
    "CO": "co",
    "OZONE": "o3",
    "O3": "o3",
    "NH3": "nh3",
}


@dataclass(frozen=True)
class CpcbRecord:
    station: str
    city: str | None
    state: str | None
    lat: float | None
    lon: float | None
    hour: datetime  # UTC
    pollutant: str
    value: float | None


def _float(raw) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "" or s.upper() in {"NA", "N/A", "NONE", "-"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_last_update(raw: str) -> datetime:
    """'23-11-2026 16:00:00' (IST) -> start of the hour it closes, in UTC.

    `last_update` marks the END of the averaging period: values stamped 16:00 IST include the
    hour 15:00-16:00 IST. Checked against OpenAQ hourly data for the same stations
    (2026-11-23): windows ending at 16:00 IST match CPCB's sub-indices within ~1% for PM10,
    NO2, SO2 and CO. So the reading belongs to the hour starting 15:00 IST (09:30 UTC).
    """
    local = datetime.strptime(raw.strip(), "%d-%m-%Y %H:%M:%S")
    return floor_hour((local - IST_OFFSET - timedelta(hours=1)).replace(tzinfo=UTC))


def parse_records(records: list[dict]) -> tuple[list[CpcbRecord], int]:
    """Parse and de-duplicate feed rows. Returns (records, rows_skipped_as_unparseable)."""
    by_key: dict[tuple[str, str], CpcbRecord] = {}
    bad = 0
    for r in records:
        pollutant = POLLUTANT_MAP.get(str(r.get("pollutant_id", "")).strip().upper())
        station = str(r.get("station", "")).strip()
        try:
            hour = parse_last_update(r["last_update"])
        except (KeyError, ValueError):
            bad += 1
            continue
        if not pollutant or not station:
            bad += 1
            continue
        value = _float(r.get("avg_value", r.get("pollutant_avg")))
        rec = CpcbRecord(
            station=station,
            city=(r.get("city") or "").strip() or None,
            state=(r.get("state") or "").strip() or None,
            lat=_float(r.get("latitude")),
            lon=_float(r.get("longitude")),
            hour=hour,
            pollutant=pollutant,
            value=value,
        )
        key = (station, pollutant)
        if key not in by_key or rec.hour >= by_key[key].hour:
            by_key[key] = rec
    return list(by_key.values()), bad


def fetch_all(http: HttpClient, api_key: str) -> list[dict]:
    records: list[dict] = []
    offset = 0
    while True:
        page = http.get_json(
            URL,
            {"api-key": api_key, "format": "json", "limit": PAGE_SIZE, "offset": offset},
        )
        batch = page.get("records") or []
        records.extend(batch)
        total = int(page.get("total") or 0)
        offset += PAGE_SIZE
        if not batch or offset >= total:
            return records


def store(
    session: Session,
    records: list[CpcbRecord],
    districts: list[DistrictRow],
    fetched_at: datetime,
) -> int:
    """Upsert stations and readings, then write 'missing' rows. Returns rows written."""
    if not records:
        return 0

    # Stations
    stations: dict[str, CpcbRecord] = {}
    for rec in records:
        stations.setdefault(rec.station, rec)
    station_rows = [
        {
            "source": "cpcb",
            "external_id": name,
            "name": name,
            "city": rec.city,
            "state": rec.state,
            "lat": rec.lat,
            "lon": rec.lon,
            "district_id": nearest_district(districts, rec.lat, rec.lon),
            "is_active": True,
            "last_seen_at": fetched_at,
        }
        for name, rec in stations.items()
    ]
    upsert(session, Station.__table__, station_rows, ["source", "external_id"])
    ids = dict(
        session.execute(
            select(Station.external_id, Station.id).where(
                Station.source == "cpcb", Station.external_id.in_(list(stations))
            )
        ).all()
    )

    # Readings that arrived (or arrived as NA)
    rows = []
    for rec in records:
        base = {
            "station_id": ids[rec.station],
            "hour": rec.hour,
            "pollutant": rec.pollutant,
            "unit": UNIT,
            "source": "cpcb",
            "fetched_at": fetched_at,
        }
        if rec.value is None:
            rows.append({**base, "value": None, "status": "missing", "reason": "reported_na"})
        else:
            rows.append({**base, "value": rec.value, "status": "ok", "reason": None})
    ok_rows = [r for r in rows if r["status"] == "ok"]
    na_rows = [r for r in rows if r["status"] != "ok"]
    written = upsert(session, Reading.__table__, ok_rows, ["station_id", "hour", "pollutant"])
    # Never let a missing marker overwrite a real value.
    written += upsert(
        session, Reading.__table__, na_rows, ["station_id", "hour", "pollutant"], do_nothing=True
    )

    # Missing rows at the snapshot hour for every expected (station, pollutant).
    snapshot_hour = max(rec.hour for rec in records)
    written += mark_missing(session, snapshot_hour, fetched_at)

    # Stations silent for a week stop being expected.
    session.execute(
        update(Station)
        .where(
            Station.source == "cpcb",
            Station.last_seen_at < fetched_at - timedelta(days=INACTIVE_AFTER_DAYS),
        )
        .values(is_active=False)
    )
    return written


MARK_MISSING_SQL = text(
    """
    INSERT INTO readings (station_id, hour, pollutant, value, unit, status, reason, source,
                          fetched_at)
    SELECT e.station_id, :hour, e.pollutant, NULL, :unit, 'missing', 'not_in_feed', 'cpcb',
           :fetched_at
    FROM (
        SELECT DISTINCT r.station_id, r.pollutant
        FROM readings r
        JOIN stations s ON s.id = r.station_id
        WHERE s.source = 'cpcb' AND s.is_active AND r.status <> 'missing'
    ) e
    ON CONFLICT (station_id, hour, pollutant) DO NOTHING
    RETURNING id
    """
)


def mark_missing(session: Session, hour: datetime, fetched_at: datetime) -> int:
    result = session.execute(
        MARK_MISSING_SQL, {"hour": hour, "unit": UNIT, "fetched_at": fetched_at}
    )
    return len(result.all())


def run(session: Session, http: HttpClient, districts: list[DistrictRow], stats: RunStats):
    api_key = get_settings().data_gov_in_api_key
    if not api_key:
        stats.skipped = True
        stats.notes.append("DATA_GOV_IN_API_KEY not set")
        return
    fetched_at = utc_now()
    raw = fetch_all(http, api_key)
    records, bad = parse_records(raw)
    stats.errors += bad
    stats.rows += store(session, records, districts, fetched_at)
    stats.notes.append(f"{len(raw)} feed rows, {len(records)} unique station-pollutants")
    if bad:
        stats.notes.append(f"{bad} unparseable rows skipped")
