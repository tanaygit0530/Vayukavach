"""Daily city AQI from station daily mean concentrations (the forecasting target).

Rules (CPCB): a pollutant's daily value needs >= 16 observed hours; a station AQI needs >= 3
pollutants including PM2.5 or PM10; the city AQI is the mean of valid station AQIs.
This uses the sub-index of the daily MEAN concentration (daily data has no hourly detail);
for the same data it runs a little above CPCB's feed method on polluted days, consistently
across history and forecasts.
"""

from __future__ import annotations

import pandas as pd

from app.analysis.aqi import aqi_from_concentrations
from app.analysis.aqi_breakpoints import MIN_HOURS_24H

POLLUTANTS = ("pm25", "pm10", "no2", "so2", "co", "o3")


def city_daily(station_days: pd.DataFrame) -> pd.DataFrame:
    """station_days: station_id, date, pollutant, value, observed_hours.
    Returns per date: aqi, stations, and the city mean of each pollutant."""
    cols = ["date", "aqi", "stations", *POLLUTANTS]
    if station_days.empty:
        return pd.DataFrame(columns=cols)
    ok = station_days[
        (station_days["observed_hours"] >= MIN_HOURS_24H)
        & station_days["value"].notna()
        & (station_days["value"] >= 0)
        & station_days["pollutant"].isin(POLLUTANTS)
    ]
    wide = ok.pivot_table(index=["date", "station_id"], columns="pollutant", values="value")
    rows = []
    for day, block in wide.groupby(level="date"):
        aqis = []
        for _, station in block.iterrows():
            result = aqi_from_concentrations({p: station.get(p) for p in POLLUTANTS})
            if result.valid and result.aqi is not None:
                aqis.append(result.aqi)
        means = {p: (float(block[p].mean()) if p in block and block[p].notna().any() else None)
                 for p in POLLUTANTS}  # fmt: skip
        rows.append(
            {
                "date": day,
                "aqi": int(round(sum(aqis) / len(aqis))) if aqis else None,
                "stations": len(aqis),
                **means,
            }
        )
    return pd.DataFrame(rows, columns=cols)


def station_days_from_hourly(readings: pd.DataFrame) -> pd.DataFrame:
    """Hourly readings (station_id, hour, pollutant, status, value) -> daily means per IST day."""
    if readings.empty:
        return pd.DataFrame(columns=["station_id", "date", "pollutant", "value", "observed_hours"])
    ok = readings[readings["status"].isin({"ok", "excluded_over_999"}) & readings["value"].notna()]
    ok = ok.assign(date=(ok["hour"] + pd.Timedelta(hours=5, minutes=30)).dt.date)
    g = ok.groupby(["station_id", "date", "pollutant"])["value"]
    out = pd.DataFrame({"value": g.mean(), "observed_hours": g.count()}).reset_index()
    return out
