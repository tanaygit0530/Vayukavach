from datetime import date

import pandas as pd

from app.forecast.daily_aqi import city_daily, station_days_from_hourly

D = date(2026, 11, 1)


def _rows(station, values, hours=24):
    return [(station, D, p, v, hours) for p, v in values.items()]


def test_city_aqi_is_mean_of_valid_station_aqis():
    df = pd.DataFrame(
        _rows(1, {"pm25": 150, "pm10": 200, "no2": 50})  # AQI 323
        + _rows(2, {"pm25": 60, "pm10": 100, "no2": 40})  # AQI 100
        + _rows(3, {"pm25": 300}),  # only 1 pollutant: not a valid station AQI
        columns=["station_id", "date", "pollutant", "value", "observed_hours"],
    )
    out = city_daily(df).iloc[0]
    assert out.aqi == round((323 + 100) / 2) and out.stations == 2
    assert out.pm25 == (150 + 60 + 300) / 3  # pollutant means use every station


def test_needs_16_hours():
    df = pd.DataFrame(
        _rows(1, {"pm25": 150, "pm10": 200, "no2": 50}, hours=15),
        columns=["station_id", "date", "pollutant", "value", "observed_hours"],
    )
    assert city_daily(df).empty  # a day without 16 h of data is not a training target


def test_daily_means_from_hourly_readings_use_ist_days():
    hours = pd.date_range("2026-10-31T18:30Z", periods=24, freq="1h")  # 1 Nov IST
    readings = pd.DataFrame(
        {"station_id": 1, "hour": hours, "pollutant": "pm25", "status": "ok", "value": 100.0}
    )
    readings.loc[0, "status"] = "missing"
    readings.loc[0, "value"] = None
    out = station_days_from_hourly(readings)
    assert len(out) == 1 and out.iloc[0].date == D
    assert out.iloc[0].observed_hours == 23 and out.iloc[0].value == 100.0
