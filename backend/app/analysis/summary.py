"""Build daily_city_summary and station_day_completeness for a district and IST day.

Inputs:
- Hourly concentrations from reference monitors (OpenAQ mirror of CPCB/SPCB stations, which
  keeps a full hourly history). Low-cost sensors are not used here.
- CPCB's published sub-indices (data.gov.in snapshots) for the official figure.
- CAMS model PM2.5 for the district, to rank hours by pollution for the gap-bias check.

Real readings are never overwritten: the shadow AQI is computed on a copy.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.analysis.aqi import DAILY, RUNNING, AqiResult, station_aqi
from app.analysis.completeness import (
    RECEIVED,
    overall_pct,
    silence_report,
    silent_matrix,
    station_day_completeness,
)
from app.analysis.gap_bias import excluded_readings, hourly_missing_rate, missing_when_it_mattered
from app.analysis.hourly import running_city_aqi
from app.analysis.shadow import fill_missing, validate_holdout
from app.analysis.time import day_bounds, day_hours
from app.models import CityHourAqi, DailyCitySummary, District, StationDayCompleteness

BULLETIN_HOUR_IST = 16  # CPCB's daily AQI bulletin is the 4 PM value
# Hourly data reaches OpenAQ 1-2 hours late; newer hours are not judged as missing yet.
SETTLE_HOURS = 2
COLUMNS = ["station_id", "hour", "pollutant", "status", "value"]


# ---------------------------------------------------------------- loading


def load_reference_stations(session: Session, district_id: int) -> dict[int, tuple[float, float]]:
    rows = session.execute(
        text(
            "SELECT id, lat, lon FROM stations WHERE district_id = :d AND source = 'openaq'"
            " AND is_reference AND lat IS NOT NULL"
        ),
        {"d": district_id},
    ).all()
    return {r.id: (r.lat, r.lon) for r in rows}


def load_readings(
    session: Session, station_ids: list[int], start: datetime, end: datetime
) -> pd.DataFrame:
    if not station_ids:
        return pd.DataFrame(columns=COLUMNS)
    rows = session.execute(
        text(
            "SELECT station_id, hour, pollutant, status, value FROM readings"
            " WHERE station_id = ANY(:ids) AND hour >= :s AND hour < :e"
        ),
        {"ids": station_ids, "s": start, "e": end},
    ).all()
    df = pd.DataFrame(rows, columns=COLUMNS)
    if not df.empty:
        df["hour"] = pd.to_datetime(df["hour"], utc=True)
        df["value"] = df["value"].astype(float)
    return df


def load_model_pm25(session: Session, district_id: int, start: datetime, end: datetime):
    rows = session.execute(
        text(
            "SELECT hour, value FROM model_air WHERE district_id = :d AND pollutant = 'pm25'"
            " AND hour >= :s AND hour < :e AND value IS NOT NULL"
        ),
        {"d": district_id, "s": start, "e": end},
    ).all()
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series([r.value for r in rows], index=pd.to_datetime([r.hour for r in rows], utc=True))
    return s.groupby(level=0).mean()


@dataclass(frozen=True)
class Official:
    aqi: int | None
    hour: datetime | None
    stations: int


def official_from_cpcb(session: Session, district_id: int, day: date, end: datetime) -> Official:
    """City figure from CPCB's published station sub-indices: each station's AQI is its
    highest sub-index; the city value is the mean over stations (as in CPCB bulletins)."""
    start, _ = day_bounds(day)
    rows = session.execute(
        text(
            "SELECT r.station_id, r.hour, max(r.value) AS aqi FROM readings r"
            " JOIN stations s ON s.id = r.station_id"
            " WHERE s.district_id = :d AND s.source = 'cpcb' AND r.status = 'ok'"
            " AND r.unit = 'aqi_subindex' AND r.hour >= :s AND r.hour < :e"
            " GROUP BY r.station_id, r.hour"
        ),
        {"d": district_id, "s": start, "e": end},
    ).all()
    if not rows:
        return Official(None, None, 0)
    df = pd.DataFrame(rows, columns=["station_id", "hour", "aqi"])
    df["hour"] = pd.to_datetime(df["hour"], utc=True)
    bulletin = start + timedelta(hours=BULLETIN_HOUR_IST)
    hour = pd.Timestamp(bulletin) if (df["hour"] == bulletin).any() else df["hour"].max()
    at = df[df["hour"] == hour]
    return Official(round(float(at["aqi"].mean())), hour.to_pydatetime(), len(at))


# ---------------------------------------------------------------- AQI per city


def _frames(readings: pd.DataFrame, statuses: frozenset[str], hours: pd.DatetimeIndex):
    """{pollutant: DataFrame(hour x station)} with NaN where no usable value."""
    frames = {}
    for pollutant, rows in readings.groupby("pollutant"):
        usable = rows[rows["status"].isin(statuses)]
        frame = usable.pivot_table(index="hour", columns="station_id", values="value")
        stations = sorted(rows["station_id"].unique())
        frames[pollutant] = frame.reindex(index=hours, columns=stations)
    return frames


def _station_results(
    frames: Mapping[str, pd.DataFrame], end: datetime, mode: str = DAILY
) -> dict[int, AqiResult]:
    stations = sorted({s for f in frames.values() for s in f.columns})
    return {
        s: station_aqi({p: f[s] for p, f in frames.items() if s in f.columns}, end, mode)
        for s in stations
    }


@dataclass(frozen=True)
class CityAqi:
    aqi: int | None
    main_pollutant: str | None
    stations: int


def city_aqi(results: Mapping[int, AqiResult]) -> CityAqi:
    valid = [r for r in results.values() if r.valid and r.aqi is not None]
    if not valid:
        return CityAqi(None, None, 0)
    main = Counter(r.main_pollutant for r in valid).most_common(1)[0][0]
    return CityAqi(round(sum(r.aqi for r in valid) / len(valid)), main, len(valid))


@dataclass(frozen=True)
class ShadowResult:
    city: CityAqi
    low: int | None
    high: int | None
    filled: int
    unfilled: int
    mae: dict[str, float]
    validation_n: dict[str, int]


def shadow_city_aqi(
    readings: pd.DataFrame,
    coords: Mapping[int, tuple[float, float]],
    hours: pd.DatetimeIndex,
    end: datetime,
    mode: str = DAILY,
) -> ShadowResult:
    real = _frames(readings, RECEIVED, hours)
    filled_frames, low_frames, high_frames = {}, {}, {}
    filled_n = unfilled_n = 0
    mae: dict[str, float] = {}
    val_n: dict[str, int] = {}
    for pollutant, frame in real.items():
        filled, mask = fill_missing(frame, coords)
        check = validate_holdout(frame, coords)
        err = check.mae or 0.0
        if check.mae is not None:
            mae[pollutant], val_n[pollutant] = round(check.mae, 2), check.n
        filled_frames[pollutant] = filled
        low_frames[pollutant] = filled.where(~mask, (filled - err).clip(lower=0))
        high_frames[pollutant] = filled.where(~mask, filled + err)
        filled_n += int(mask.to_numpy().sum())
        unfilled_n += int(filled.isna().to_numpy().sum())
    city = city_aqi(_station_results(filled_frames, end, mode))
    low = city_aqi(_station_results(low_frames, end, mode)).aqi
    high = city_aqi(_station_results(high_frames, end, mode)).aqi
    return ShadowResult(city, low, high, filled_n, unfilled_n, mae, val_n)


# ---------------------------------------------------------------- build


def build_city_day(session: Session, district: District, day: date, now: datetime) -> dict | None:
    """Compute and store the summary for one district and IST day. Returns the row."""
    day_start, day_end = day_bounds(day)
    settled = now - timedelta(hours=SETTLE_HOURS)
    hours_done = day_hours(day, settled)
    if len(hours_done) == 0:
        return None
    end = hours_done[-1].to_pydatetime() + timedelta(hours=1)
    window = pd.date_range(end - timedelta(hours=24), end, freq="1h", inclusive="left")

    known = load_reference_stations(session, district.id)
    readings = load_readings(session, list(known), min(window[0], day_start), end)
    # Only stations with any row in the window are expected to report (others have not
    # been collected yet, or retired).
    with_data = set(readings["station_id"].unique()) if not readings.empty else set()
    coords = {s: c for s, c in known.items() if s in with_data}
    day_rows = readings[readings["hour"] >= day_start] if not readings.empty else readings
    window_rows = readings[readings["hour"] >= window[0]] if not readings.empty else readings

    per_station = station_day_completeness(day_rows, day, settled)
    silence = silence_report(silent_matrix(day_rows, day, settled))

    level = load_model_pm25(session, district.id, day_start, end)
    level_source = "cams"
    if level.empty and not day_rows.empty:
        pm = day_rows[(day_rows["pollutant"] == "pm25") & day_rows["status"].isin(RECEIVED)]
        level = pm.groupby("hour")["value"].mean()
        level_source = "stations"
    gap = missing_when_it_mattered(
        level, hourly_missing_rate(day_rows, day, settled, pollutants={"pm25", "pm10"})
    )
    excluded = excluded_readings(day_rows) if not day_rows.empty else pd.DataFrame()

    mode = RUNNING if end < day_end else DAILY  # today: index "now"; past days: daily
    measured = city_aqi(
        _station_results(_frames(window_rows, frozenset({"ok"}), window), end, mode)
    )
    shadow = shadow_city_aqi(window_rows, coords, window, end, mode)
    # CPCB's feed is a live snapshot (no publishing lag): use every hour up to now.
    official = official_from_cpcb(session, district.id, day, min(now, day_end))

    computed_at = datetime.now(UTC)
    row = {
        "district_id": district.id,
        "date": day,
        "is_partial_day": end < day_end,
        "hours_covered": len(hours_done),
        "official_aqi": official.aqi,
        "official_hour": official.hour,
        "official_stations": official.stations,
        "measured_aqi": measured.aqi,
        "measured_main_pollutant": measured.main_pollutant,
        "measured_stations": measured.stations,
        "shadow_aqi": shadow.city.aqi,
        "shadow_aqi_low": shadow.low,
        "shadow_aqi_high": shadow.high,
        "shadow_main_pollutant": shadow.city.main_pollutant,
        "shadow_stations": shadow.city.stations,
        "filled_hours": shadow.filled,
        "unfilled_hours": shadow.unfilled,
        "shadow_mae_pm25": shadow.mae.get("pm25"),
        "shadow_validation_n": shadow.validation_n.get("pm25", 0),
        "completeness_pct": overall_pct(per_station),
        "expected_readings": int(per_station["expected"].sum()) if len(per_station) else 0,
        "received_readings": int(per_station["received"].sum()) if len(per_station) else 0,
        "stations_total": len(coords),
        "stations_silent": len(silence.silent_stations),
        "city_silent_hours": len(silence.city_silent_hours),
        "max_share_silent": round(silence.max_share_silent, 3),
        "gap_bias_flag": gap.flagged if gap else None,
        "gap_bias_diff_pp": gap.diff_pp if gap else None,
        "polluted_missing_pct": gap.polluted_missing_pct if gap else None,
        "clean_missing_pct": gap.clean_missing_pct if gap else None,
        "gap_bias_level_source": level_source if gap else None,
        "excluded_count": int((excluded["status"] == "excluded_over_999").sum())
        if len(excluded)
        else 0,
        "near_limit_count": len(excluded),
        "computed_at": computed_at,
    }
    stmt = insert(DailyCitySummary).values(row)
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=["district_id", "date"],
            set_={k: stmt.excluded[k] for k in row if k not in ("district_id", "date")},
        )
    )
    if len(per_station):
        comp_rows = [
            {**r, "date": day, "computed_at": computed_at, "station_id": int(r["station_id"])}
            for r in per_station.to_dict("records")
        ]
        stmt = insert(StationDayCompleteness).values(comp_rows)
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["station_id", "date", "pollutant"],
                set_={
                    k: stmt.excluded[k]
                    for k in (
                        "expected",
                        "received",
                        "excluded",
                        "pct",
                        "longest_gap_hours",
                        "computed_at",
                    )  # fmt: skip
                },
            )
        )
    return row


# ---------------------------------------------------------------- hourly series

HOURLY_LOOKBACK_HOURS = 48
AQI_POLLUTANTS = ("pm25", "pm10", "no2", "so2", "co", "o3", "nh3")


def official_hourly(session: Session, district_id: int, start: datetime, end: datetime):
    """Per hour: CPCB city AQI (mean of station max sub-indices) and main pollutant."""
    rows = session.execute(
        text(
            "SELECT r.station_id, r.hour, r.pollutant, r.value FROM readings r"
            " JOIN stations s ON s.id = r.station_id"
            " WHERE s.district_id = :d AND s.source = 'cpcb' AND r.status = 'ok'"
            " AND r.unit = 'aqi_subindex' AND r.hour >= :s AND r.hour < :e"
        ),
        {"d": district_id, "s": start, "e": end},
    ).all()
    if not rows:
        return pd.DataFrame(columns=["aqi", "main_pollutant", "stations"])
    df = pd.DataFrame(rows, columns=["station_id", "hour", "pollutant", "value"])
    df["hour"] = pd.to_datetime(df["hour"], utc=True)
    top = df.loc[df.groupby(["hour", "station_id"])["value"].idxmax()]
    out = top.groupby("hour").agg(
        aqi=("value", lambda v: int(round(float(v.round().mean())))),
        main_pollutant=("pollutant", lambda p: p.value_counts().idxmax()),
        stations=("station_id", "nunique"),
    )
    return out


def cams_hourly(session: Session, district_id: int, start: datetime) -> pd.DataFrame:
    rows = session.execute(
        text(
            "SELECT hour, pollutant, value, is_forecast FROM model_air WHERE district_id = :d"
            " AND hour >= :s AND pollutant = ANY(:p) AND value IS NOT NULL"
        ),
        {"d": district_id, "s": start, "p": list(AQI_POLLUTANTS)},
    ).all()
    if not rows:
        return pd.DataFrame(columns=["aqi", "main_pollutant", "stations"])
    df = pd.DataFrame(rows, columns=["hour", "pollutant", "value", "is_forecast"])
    df["hour"] = pd.to_datetime(df["hour"], utc=True)
    frames = {
        p: g.groupby("hour")["value"].mean().to_frame(name=0) for p, g in df.groupby("pollutant")
    }
    return running_city_aqi(frames)


def build_city_hours(session: Session, district: District, now: datetime) -> int:
    """Store the last 48 h (official / measured / shadow / CAMS) and CAMS forecast hours."""
    end_live = floor_ist_hour(now)  # hours fully ended (CPCB feed: live)
    end_settled = floor_ist_hour(now - timedelta(hours=SETTLE_HOURS))  # OpenAQ settled
    out_start = end_live - timedelta(hours=HOURLY_LOOKBACK_HOURS)
    warmup = out_start - timedelta(hours=24)

    official = official_hourly(session, district.id, out_start, end_live)
    known = load_reference_stations(session, district.id)
    readings = load_readings(session, list(known), warmup, end_settled)
    hours = pd.date_range(warmup, end_settled, freq="1h", inclusive="left")
    measured = shadow = low = high = pd.DataFrame(columns=["aqi", "main_pollutant", "stations"])
    if not readings.empty and len(hours):
        coords = {s: c for s, c in known.items() if s in set(readings["station_id"])}
        measured = running_city_aqi(_frames(readings, frozenset({"ok"}), hours))
        real = _frames(readings, RECEIVED, hours)
        filled, lows, highs = {}, {}, {}
        for pollutant, frame in real.items():
            f, mask = fill_missing(frame, coords)
            err = validate_holdout(frame, coords).mae or 0.0
            filled[pollutant] = f
            lows[pollutant] = f.where(~mask, (f - err).clip(lower=0))
            highs[pollutant] = f.where(~mask, f + err)
        shadow = running_city_aqi(filled)
        low = running_city_aqi(lows)
        high = running_city_aqi(highs)
    cams = cams_hourly(session, district.id, warmup)

    def at(frame: pd.DataFrame, hour, col):
        if hour not in frame.index:
            return None
        value = frame.at[hour, col]
        return None if pd.isna(value) else (int(value) if col != "main_pollutant" else value)

    computed_at = datetime.now(UTC)
    all_hours = sorted(
        {h for h in pd.date_range(out_start, end_live, freq="1h", inclusive="left")}
        | {h for h in cams.index if h >= out_start}
    )
    rows = []
    for hour in all_hours:
        rows.append(
            {
                "district_id": district.id,
                "hour": hour.to_pydatetime(),
                "official_aqi": at(official, hour, "aqi"),
                "official_main_pollutant": at(official, hour, "main_pollutant"),
                "official_stations": at(official, hour, "stations") or 0,
                "measured_aqi": at(measured, hour, "aqi"),
                "measured_main_pollutant": at(measured, hour, "main_pollutant"),
                "measured_stations": at(measured, hour, "stations") or 0,
                "shadow_aqi": at(shadow, hour, "aqi"),
                "shadow_aqi_low": at(low, hour, "aqi"),
                "shadow_aqi_high": at(high, hour, "aqi"),
                "cams_aqi": at(cams, hour, "aqi"),
                "cams_main_pollutant": at(cams, hour, "main_pollutant"),
                "is_forecast": hour >= end_live,
                "computed_at": computed_at,
            }
        )
    if rows:
        stmt = insert(CityHourAqi).values(rows)
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["district_id", "hour"],
                set_={k: stmt.excluded[k] for k in rows[0] if k not in ("district_id", "hour")},
            )
        )
    return len(rows)


def floor_ist_hour(ts: datetime) -> datetime:
    """Start of the IST clock hour containing ts, in UTC (hh:30 UTC)."""
    shifted = pd.Timestamp(ts).tz_convert("UTC") + pd.Timedelta(minutes=30)
    return (shifted.floor("h") - pd.Timedelta(minutes=30)).to_pydatetime()


def build_recent(session: Session, days: int = 2, now: datetime | None = None) -> list[dict]:
    """Summaries for the last `days` IST days (today included) for every district."""
    now = now or datetime.now(UTC)
    today = (now + timedelta(hours=5, minutes=30)).date()
    out = []
    for district in session.execute(select(District).order_by(District.id)).scalars():
        for offset in range(days - 1, -1, -1):
            row = build_city_day(session, district, today - timedelta(days=offset), now)
            if row:
                out.append(row)
        build_city_hours(session, district, now)
    session.commit()
    return out
