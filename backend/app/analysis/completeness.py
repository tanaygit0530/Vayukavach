"""Data completeness: how many expected hourly readings actually arrived.

Input everywhere is a DataFrame of readings with columns
    station_id, hour (UTC, tz-aware, IST hour grid), pollutant, status, value
where status is 'ok', 'missing' or 'excluded_over_999'. Hours with no row at all are
counted as missing too: an hour nobody recorded is still an hour without data.

Wording rule: this measures completeness and reliability, nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from app.analysis.time import day_hours

RECEIVED = frozenset({"ok", "excluded_over_999"})  # a value arrived (even if CPCB drops it)
SILENT_RUN_HOURS = 3
CITY_SILENT_SHARE = 0.25


def _received_matrix(readings: pd.DataFrame, hours: pd.DatetimeIndex) -> pd.DataFrame:
    """Index: hours; columns: (station_id, pollutant); True where a value arrived."""
    if readings.empty:
        return pd.DataFrame(index=hours)
    df = readings[readings["hour"].isin(hours)].copy()
    df["received"] = df["status"].isin(RECEIVED)
    expected_cols = pd.MultiIndex.from_frame(
        readings[["station_id", "pollutant"]]
        .drop_duplicates()
        .sort_values(["station_id", "pollutant"])
    )
    matrix = df.pivot_table(
        index="hour", columns=["station_id", "pollutant"], values="received", aggfunc="max"
    )
    matrix = matrix.reindex(index=hours, columns=expected_cols)
    return matrix.fillna(False).astype(bool)


def longest_run(flags: pd.Series) -> int:
    """Length of the longest run of True values."""
    best = run = 0
    for flag in flags:
        run = run + 1 if flag else 0
        best = max(best, run)
    return best


def runs(flags: pd.Series, min_len: int) -> list[tuple[datetime, datetime]]:
    """[(first_hour, last_hour)] for each run of True of at least `min_len` hours."""
    out: list[tuple[datetime, datetime]] = []
    start = prev = None
    length = 0
    for hour, flag in flags.items():
        if flag:
            start = hour if start is None else start
            prev, length = hour, length + 1
        else:
            if start is not None and length >= min_len:
                out.append((start, prev))
            start, length = None, 0
    if start is not None and length >= min_len:
        out.append((start, prev))
    return out


def station_day_completeness(
    readings: pd.DataFrame, day: date, now: datetime | None = None
) -> pd.DataFrame:
    """One row per (station, pollutant): expected, received, excluded, pct, longest gap."""
    hours = day_hours(day, now)
    matrix = _received_matrix(readings, hours)
    cols = ["station_id", "pollutant", "expected", "received", "excluded", "pct",
            "longest_gap_hours"]  # fmt: skip
    if matrix.empty or len(hours) == 0:
        return pd.DataFrame(columns=cols)
    day_rows = readings[readings["hour"].isin(hours)]
    excluded = (
        day_rows[day_rows["status"] == "excluded_over_999"]
        .groupby(["station_id", "pollutant"])
        .size()
    )
    rows = []
    for (station_id, pollutant), received in matrix.items():
        n_received = int(received.sum())
        rows.append(
            {
                "station_id": station_id,
                "pollutant": pollutant,
                "expected": len(hours),
                "received": n_received,
                "excluded": int(excluded.get((station_id, pollutant), 0)),
                "pct": round(100.0 * n_received / len(hours), 1),
                "longest_gap_hours": longest_run(~received),
            }
        )
    return pd.DataFrame(rows, columns=cols)


def silent_matrix(readings: pd.DataFrame, day: date, now: datetime | None = None) -> pd.DataFrame:
    """Index: hours; columns: station_id; True when the station sent nothing that hour."""
    hours = day_hours(day, now)
    matrix = _received_matrix(readings, hours)
    if matrix.empty:
        return pd.DataFrame(index=hours)
    return ~matrix.T.groupby(level="station_id").any().T


@dataclass(frozen=True)
class SilenceReport:
    silent_stations: dict[int, list[tuple[datetime, datetime]]]  # runs of >= 3 hours
    city_silent_hours: list[datetime]  # hours when >= 25% of stations were silent
    max_share_silent: float  # worst hour, 0..1


def silence_report(
    silent: pd.DataFrame,
    min_run: int = SILENT_RUN_HOURS,
    city_share: float = CITY_SILENT_SHARE,
) -> SilenceReport:
    if silent.empty or silent.shape[1] == 0:
        return SilenceReport({}, [], 0.0)
    stations = {}
    for station_id, flags in silent.items():
        found = runs(flags, min_run)
        if found:
            stations[int(station_id)] = found
    share = silent.mean(axis=1)
    return SilenceReport(
        silent_stations=stations,
        city_silent_hours=[h.to_pydatetime() for h in share[share >= city_share].index],
        max_share_silent=float(share.max()),
    )


def overall_pct(station_day: pd.DataFrame) -> float | None:
    """City completeness: received / expected over all station-pollutant-hours."""
    if station_day.empty or station_day["expected"].sum() == 0:
        return None
    return round(100.0 * station_day["received"].sum() / station_day["expected"].sum(), 1)
