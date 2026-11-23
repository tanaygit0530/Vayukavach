"""Running (hour-by-hour) city AQI, vectorised.

Same rules as app.analysis.aqi with the CPCB_FEED method:
- 24-h pollutants: mean of the hourly sub-indices over the last 24 h (>= 16 valid hours)
- CO, O3: sub-index of the mean concentration over the last 8 h (>= 6 valid hours)
- station AQI = highest sub-index; valid with >= 3 pollutants including PM2.5 or PM10
- city AQI = mean of the valid station AQIs; main pollutant = most common station main

Input frames are indexed by consecutive hourly timestamps (hour starts); the value for hour h
uses the window ending with h (i.e. CPCB's index published at the end of hour h).
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from app.analysis.aqi import sub_index
from app.analysis.aqi_breakpoints import (
    EIGHT_HOUR,
    MIN_HOURS_8H,
    MIN_HOURS_24H,
    MIN_POLLUTANTS,
    REQUIRED_ONE_OF,
)

_sub = np.vectorize(lambda p, c: np.nan if (s := sub_index(p, c)) is None else s, otypes=[float])


def _regular(frame: pd.DataFrame) -> pd.DataFrame:
    """Reindex to a gap-free hourly index so rolling windows count hours, not rows."""
    if frame.empty:
        return frame
    full = pd.date_range(frame.index.min(), frame.index.max(), freq="1h")
    return frame.reindex(full)


def running_sub_indices(pollutant: str, frame: pd.DataFrame) -> pd.DataFrame:
    """(hour x station) running sub-index for one pollutant."""
    frame = _regular(frame.astype(float).where(frame >= 0))
    if pollutant in EIGHT_HOUR:
        mean8 = frame.rolling(8, min_periods=MIN_HOURS_8H).mean()
        values = mean8.to_numpy()
        out = np.full(values.shape, np.nan)
        ok = ~np.isnan(values)
        out[ok] = _sub(pollutant, values[ok])
        return pd.DataFrame(out, index=frame.index, columns=frame.columns)
    values = frame.to_numpy()
    subs = np.full(values.shape, np.nan)
    ok = ~np.isnan(values)
    subs[ok] = _sub(pollutant, values[ok])
    subs = pd.DataFrame(subs, index=frame.index, columns=frame.columns)
    return subs.rolling(24, min_periods=MIN_HOURS_24H).mean()


def running_city_aqi(frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Per hour: aqi (rounded mean of valid station AQIs), main_pollutant, stations."""
    subs = {p: running_sub_indices(p, f) for p, f in frames.items() if not f.empty}
    if not subs:
        return pd.DataFrame(columns=["aqi", "main_pollutant", "stations"])
    index = sorted(set().union(*(s.index for s in subs.values())))
    stations = sorted(set().union(*(s.columns for s in subs.values())))
    cube = {p: s.reindex(index=index, columns=stations) for p, s in subs.items()}
    pollutants = list(cube)
    stack = np.stack([cube[p].to_numpy() for p in pollutants])  # (pollutant, hour, station)
    have = ~np.isnan(stack)
    count = have.sum(axis=0)
    has_pm = np.zeros(count.shape, dtype=bool)
    for i, p in enumerate(pollutants):
        if p in REQUIRED_ONE_OF:
            has_pm |= have[i]
    valid = (count >= MIN_POLLUTANTS) & has_pm
    filled = np.where(have, stack, -np.inf)
    station_aqi = filled.max(axis=0)
    station_main = filled.argmax(axis=0)
    rows = []
    for h, hour in enumerate(index):
        ok = valid[h]
        if not ok.any():
            rows.append((hour, None, None, 0))
            continue
        aqis = station_aqi[h][ok]
        mains = [pollutants[i] for i in station_main[h][ok]]
        main = pd.Series(mains).value_counts().idxmax()
        rows.append((hour, int(round(float(np.round(aqis).mean()))), main, int(ok.sum())))
    out = pd.DataFrame(rows, columns=["hour", "aqi", "main_pollutant", "stations"])
    return out.set_index("hour")
