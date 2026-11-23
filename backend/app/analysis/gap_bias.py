"""'Missing when it mattered': do gaps cluster in the most polluted hours?

For a city-day, rank hours by a pollution level that does not depend on the missing
readings (CAMS model PM2.5, or the mean of stations that did report), then compare the
missing rate in the N most polluted hours with the N cleanest hours.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from app.analysis.completeness import RECEIVED, _received_matrix
from app.analysis.time import day_hours

TOP_N_HOURS = 6
FLAG_THRESHOLD_PP = 20.0  # percentage points
NEAR_LIMIT_UGM3 = 950.0  # 'near' the 999 ug/m3 cut-off
LIMIT_UGM3 = 999.0


@dataclass(frozen=True)
class GapBias:
    polluted_missing_pct: float
    clean_missing_pct: float
    diff_pp: float
    flagged: bool
    polluted_hours: list[datetime]
    clean_hours: list[datetime]


def hourly_missing_rate(
    readings: pd.DataFrame,
    day: date,
    now: datetime | None = None,
    pollutants: set[str] | None = None,
) -> pd.Series:
    """Share (0..1) of expected station-pollutant readings missing in each hour."""
    df = readings if pollutants is None else readings[readings["pollutant"].isin(pollutants)]
    matrix = _received_matrix(df, day_hours(day, now))
    if matrix.shape[1] == 0:
        return pd.Series(dtype=float)
    return 1.0 - matrix.mean(axis=1)


def missing_when_it_mattered(
    level: pd.Series,
    missing_rate: pd.Series,
    n: int = TOP_N_HOURS,
    threshold_pp: float = FLAG_THRESHOLD_PP,
) -> GapBias | None:
    """None when there are fewer than 2n hours with both a level and a missing rate."""
    both = pd.concat({"level": level, "missing": missing_rate}, axis=1).dropna()
    if len(both) < 2 * n:
        return None
    ranked = both.sort_values("level", kind="mergesort")
    clean, polluted = ranked.head(n), ranked.tail(n)
    polluted_pct = 100.0 * polluted["missing"].mean()
    clean_pct = 100.0 * clean["missing"].mean()
    diff = polluted_pct - clean_pct
    return GapBias(
        polluted_missing_pct=round(polluted_pct, 1),
        clean_missing_pct=round(clean_pct, 1),
        diff_pp=round(diff, 1),
        flagged=diff >= threshold_pp,
        polluted_hours=sorted(h.to_pydatetime() for h in polluted.index),
        clean_hours=sorted(h.to_pydatetime() for h in clean.index),
    )


def excluded_readings(readings: pd.DataFrame, near: float = NEAR_LIMIT_UGM3) -> pd.DataFrame:
    """PM readings at or near 999 ug/m3: may be left out of the official AQI."""
    pm = readings[readings["pollutant"].isin({"pm25", "pm10"})]
    mask = (pm["status"] == "excluded_over_999") | (
        pm["status"].isin(RECEIVED) & (pm["value"] >= near)
    )
    out = pm[mask].copy()
    out["at_or_over_limit"] = out["value"] >= LIMIT_UGM3
    return out
