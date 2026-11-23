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
    """AQI from already-averaged concentrations (24 h, or 8 h for CO/O3)."""
    return aqi_from_sub_indices(
        {p: sub_index(p, c) for p, c in averages.items() if p in CONCENTRATION_BANDS}
    )


def aqi_from_sub_indices(sub_indices: Mapping[str, float | None]) -> AqiResult:
    """AQI = highest sub-index. Follows CPCB's validity rule: at least 3 pollutants, one of
    them PM2.5 or PM10 (an AQI is still returned when invalid, with the reason)."""
    subs = {p: s for p, s in sub_indices.items() if s is not None}
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


RUNNING = "running"  # AQI "now": CPCB's hourly running index
DAILY = "daily"  # AQI for a whole day


def window_average(
    hourly: pd.Series, pollutant: str, end: datetime, hours: int = 24, mode: str = RUNNING
) -> float | None:
    """Average for the hours before `end` (end exclusive), per CPCB rules.

    `hourly` is indexed by hour start (tz-aware) with NaN for missing hours.
    24-h pollutants: mean of the last 24 h, if at least 16 valid hours.
    CO and O3, mode 'running': mean of the last 8 h (>= 6 valid hours). This matches CPCB's
      published running sub-indices (checked against the data.gov.in feed, 2026-11-23).
    CO and O3, mode 'daily': maximum of the running 8-h means within the window.
    """
    start = end - timedelta(hours=hours)
    window = hourly[(hourly.index >= start) & (hourly.index < end)].astype(float)
    window = window[window >= 0]  # negative values are instrument errors
    if pollutant in EIGHT_HOUR:
        if mode == RUNNING:
            last8 = window[window.index >= end - timedelta(hours=8)]
            return float(last8.mean()) if last8.count() >= MIN_HOURS_8H else None
        full = window.reindex(pd.date_range(start, end, freq="1h", inclusive="left"))
        rolling = full.rolling(8, min_periods=MIN_HOURS_8H).mean()
        best = rolling.max()
        return None if pd.isna(best) else float(best)
    if window.count() < MIN_HOURS_24H:
        return None
    return float(window.mean())


# How the 24-h sub-index is formed.
CPCB_FEED = "cpcb_feed"  # mean of the hourly sub-indices (what CPCB publishes)
CONCENTRATION_MEAN = "concentration_mean"  # sub-index of the 24-h mean concentration

# Evidence (docs/validation/aqi_vs_cpcb.md, 2026-11-23, 40 Delhi station-hours): against
# CPCB's published PM2.5 sub-indices, "sub-index of the mean" was off by MAE 26.7 points
# (bias +25.7); "mean of hourly sub-indices" by MAE 7.2. The PM2.5 scale bends at 120 ug/m3
# (3.4 -> 0.77 points per ug/m3), so the two methods differ most on polluted days. We follow
# CPCB so that official vs shadow differences come from missing data, not from method.
DEFAULT_METHOD = CPCB_FEED


def window_sub_index(
    hourly: pd.Series,
    pollutant: str,
    end: datetime,
    mode: str = RUNNING,
    method: str = DEFAULT_METHOD,
) -> float | None:
    """Sub-index for the window ending at `end` (same validity rules as window_average)."""
    if pollutant in EIGHT_HOUR or method == CONCENTRATION_MEAN:
        return sub_index(pollutant, window_average(hourly, pollutant, end, mode=mode))
    start = end - timedelta(hours=24)
    window = hourly[(hourly.index >= start) & (hourly.index < end)].astype(float)
    window = window[window >= 0].dropna()
    if window.count() < MIN_HOURS_24H:
        return None
    return float(sum(sub_index(pollutant, v) for v in window) / len(window))


def station_aqi(
    hourly_by_pollutant: Mapping[str, pd.Series],
    end: datetime,
    mode: str = RUNNING,
    method: str = DEFAULT_METHOD,
) -> AqiResult:
    """AQI for one station for the 24 h before `end`."""
    return aqi_from_sub_indices(
        {p: window_sub_index(s, p, end, mode, method) for p, s in hourly_by_pollutant.items()}
    )
