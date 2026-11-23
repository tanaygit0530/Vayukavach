"""India National AQI from raw concentrations.

I = (I_hi - I_lo) / (B_hi - B_lo) * (C - B_lo) + I_lo, AQI = highest sub-index.
Breakpoints and averaging rules: app/analysis/aqi_breakpoints.py.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd

from app.analysis.aqi_breakpoints import (
    AQI_BANDS,
    CATEGORIES,
    CONCENTRATION_BANDS,
    EIGHT_HOUR,
    MIN_HOURS_8H,
    MIN_HOURS_24H,
    MIN_POLLUTANTS,
    REQUIRED_ONE_OF,
)


def _valid(value: float | None) -> bool:
    return value is not None and not (isinstance(value, float) and math.isnan(value)) and value >= 0


def sub_index(pollutant: str, concentration: float | None) -> float | None:
    """Sub-index for one pollutant, or None when there is no valid concentration."""
    if not _valid(concentration):
        return None
    bands = CONCENTRATION_BANDS[pollutant]
    c = float(concentration)
    for (b_lo, b_hi), (i_lo, i_hi) in zip(bands, AQI_BANDS, strict=True):
        if c <= b_hi:
            # Values in the small gap between bands (e.g. 30.5 for PM2.5) take the band floor.
            c_eff = max(c, b_lo)
            return (i_hi - i_lo) / (b_hi - b_lo) * (c_eff - b_lo) + i_lo
    return 500.0  # beyond the top of the scale: capped


def category(aqi: float | None) -> tuple[str, str] | None:
    """(name, key) of the CPCB category, e.g. ('Very poor', 'verypoor')."""
    if aqi is None:
        return None
    for upper, name, key in CATEGORIES:
        if round(aqi) <= upper:
            return name, key
    return CATEGORIES[-1][1], CATEGORIES[-1][2]


@dataclass(frozen=True)
class AqiResult:
    aqi: int | None
    main_pollutant: str | None
    sub_indices: dict[str, int] = field(default_factory=dict)
    valid: bool = False
    reason: str | None = None  # why the AQI is not valid

    @property
    def category(self) -> tuple[str, str] | None:
        return category(self.aqi)


def aqi_from_concentrations(averages: Mapping[str, float | None]) -> AqiResult:
    """AQI from already-averaged concentrations (24 h, or 8 h max for CO/O3).

    Follows CPCB's validity rule: at least 3 pollutants, one of them PM2.5 or PM10.
    """
    subs = {p: sub_index(p, c) for p, c in averages.items() if p in CONCENTRATION_BANDS}
    subs = {p: s for p, s in subs.items() if s is not None}
    if not subs:
        return AqiResult(None, None, {}, False, "no pollutant data")
    main = max(subs, key=lambda p: (subs[p], p))
    rounded = {p: round(s) for p, s in subs.items()}
    if len(subs) < MIN_POLLUTANTS:
        reason = f"only {len(subs)} pollutant(s); CPCB needs {MIN_POLLUTANTS}"
    elif not REQUIRED_ONE_OF & subs.keys():
        reason = "no PM2.5 or PM10"
    else:
        reason = None
    return AqiResult(round(subs[main]), main, rounded, reason is None, reason)


def window_average(
    hourly: pd.Series, pollutant: str, end: datetime, hours: int = 24
) -> float | None:
    """Average for the `hours` hours before `end` (end exclusive), per CPCB rules.

    `hourly` is indexed by hour start (tz-aware) with NaN for missing hours.
    24-h pollutants: mean, if at least 16 valid hours.
    CO and O3: maximum of the running 8-h means (each needing >= 6 valid hours).
    """
    start = end - timedelta(hours=hours)
    window = hourly[(hourly.index >= start) & (hourly.index < end)].astype(float)
    window = window[window >= 0]  # negative values are instrument errors
    if pollutant in EIGHT_HOUR:
        full = window.reindex(pd.date_range(start, end, freq="1h", inclusive="left"))
        rolling = full.rolling(8, min_periods=MIN_HOURS_8H).mean()
        best = rolling.max()
        return None if pd.isna(best) else float(best)
    if window.count() < MIN_HOURS_24H:
        return None
    return float(window.mean())


def station_aqi(hourly_by_pollutant: Mapping[str, pd.Series], end: datetime) -> AqiResult:
    """AQI for one station for the 24 h before `end`."""
    averages = {p: window_average(s, p, end) for p, s in hourly_by_pollutant.items()}
    return aqi_from_concentrations(averages)
