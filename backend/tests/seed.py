"""Shared synthetic data: Delhi on Diwali 2026 (stations go silent as pollution peaks)."""

from datetime import timedelta

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analysis.summary import build_recent
from app.analysis.time import day_bounds, day_hours
from tests.analysis.helpers import DAY


def seed_delhi(conn):
    did = conn.execute(
        text(
            "INSERT INTO districts (slug, name, state, lat, lon) VALUES"
            " ('delhi', 'Delhi', 'Delhi', 28.61, 77.21) RETURNING id"
        )  # fmt: skip
    ).scalar_one()
    ref = []
    for i in range(4):  # four monitors ~1-3 km apart
        ref.append(
            conn.execute(
                text(
                    "INSERT INTO stations (source, external_id, name, lat, lon, district_id,"
                    " is_reference) VALUES ('openaq', :e, :n, :lat, 77.21, :d, true) RETURNING id"
                ),
                {"e": str(i), "n": f"Station {i}", "lat": 28.60 + 0.01 * i, "d": did},
            ).scalar_one()
        )
    cpcb = conn.execute(
        text(
            "INSERT INTO stations (source, external_id, name, district_id, lat, lon) VALUES"
            " ('cpcb', 'S', 'S', :d, 28.62, 77.22) RETURNING id"
        ),  # fmt: skip
        {"d": did},
    ).scalar_one()
    hours = day_hours(DAY)
    level = np.linspace(100, 400, 24)  # pollution rises through the day
    rows = []
    for h_i, hour in enumerate(hours):
        for pollutant, factor in (("pm25", 1.0), ("pm10", 1.5), ("no2", 0.2)):
            conn.execute(
                text(
                    "INSERT INTO model_air (district_id, lat, lon, hour, pollutant, value, unit,"
                    " model_run, is_forecast, fetched_at) VALUES (:d, 28.6, 77.2, :h, :p, :v,"
                    " 'ug/m3', :h, false, :h)"
                ),
                {"d": did, "h": hour, "p": pollutant, "v": float(level[h_i] * factor)},
            )
        for s_i, sid in enumerate(ref):
            silent = s_i < 2 and h_i >= 18  # two of four go silent in the 6 worst hours
            for pollutant, factor in (("pm25", 1.0), ("pm10", 1.6), ("no2", 0.3)):
                value = float(level[h_i] * factor + s_i)
                status = "ok"
                if pollutant == "pm25" and s_i == 3 and h_i == 23:
                    value, status = 1050.0, "excluded_over_999"
                if silent:
                    rows.append((sid, hour, pollutant, None, "missing"))
                else:
                    rows.append((sid, hour, pollutant, value, status))
    for sid, hour, pollutant, value, status in rows:
        conn.execute(
            text(
                "INSERT INTO readings (station_id, hour, pollutant, value, unit, status, source,"
                " fetched_at) VALUES (:s, :h, :p, :v, 'ug/m3', :st, 'openaq', now())"
            ),  # fmt: skip
            {"s": sid, "h": hour, "p": pollutant, "v": value, "st": status},
        )
    bulletin = day_bounds(DAY)[0] + timedelta(hours=16)
    for pollutant, value in (("pm25", 310.0), ("pm10", 250.0)):
        conn.execute(
            text(
                "INSERT INTO readings (station_id, hour, pollutant, value, unit, status, source,"
                " fetched_at) VALUES (:s, :h, :p, :v, 'aqi_subindex', 'ok', 'cpcb', now())"
            ),
            {"s": cpcb, "h": bulletin, "p": pollutant, "v": value},
        )
    return did


NOW = day_bounds(DAY)[0] + timedelta(hours=20, minutes=30)  # 20:30 IST on the seeded day


def _seed_weather(conn, district_id, base_temp):
    start = day_bounds(DAY)[0]
    for h in range(48):
        hour = start + timedelta(hours=h)
        local = h % 24
        temp = base_temp + 8 * np.sin((local - 8) / 24 * 2 * np.pi)
        conn.execute(
            text(
                "INSERT INTO weather (district_id, hour, temperature, apparent_temperature,"
                " humidity, dew_point, wind_speed, wind_gusts, wind_direction, pressure,"
                " cloud_cover, precipitation, precipitation_probability, visibility, uv_index,"
                " weather_code, boundary_layer_height, is_forecast, fetched_at) VALUES"
                " (:d, :h, :t, :a, 60, 12, 4, 9, 300, 1012, 10, 0, 5, 3500, :uv, 0, 250, :f,"
                " :fetched)"
            ),
            {"d": district_id, "h": hour, "t": float(temp), "a": float(temp + 1.5),
             "uv": float(max(0, 8 * np.sin((local - 6) / 12 * np.pi))) if 6 <= local <= 18
             else 0.0, "f": hour > NOW, "fetched": NOW - timedelta(minutes=20)},
        )  # fmt: skip
    for i in range(10):
        day = DAY + timedelta(days=i)
        sunrise = day_bounds(day)[0] + timedelta(hours=6, minutes=40)
        conn.execute(
            text(
                "INSERT INTO weather_daily (district_id, date, weather_code, temperature_max,"
                " temperature_min, apparent_temperature_max, apparent_temperature_min, sunrise,"
                " sunset, daylight_duration, uv_index_max, precipitation_sum,"
                " precipitation_probability_max, is_forecast, fetched_at) VALUES"
                " (:d, :day, 1, :tmax, :tmin, :tmax, :tmin, :sr, :ss, 38000, 6.5, 0, 10, :f,"
                " :fetched)"
            ),
            {"d": district_id, "day": day, "tmax": base_temp + 8, "tmin": base_temp - 8,
             "sr": sunrise, "ss": sunrise + timedelta(hours=10, minutes=40), "f": i > 0,
             "fetched": NOW - timedelta(minutes=20)},
        )  # fmt: skip


def seed_all(db_engine) -> dict:
    """Delhi on Diwali plus Shimla (CAMS only) and weather for both; daily summaries built."""
    with db_engine.begin() as conn:
        delhi = seed_delhi(conn)
        shimla = conn.execute(
            text(
                "INSERT INTO districts (slug, name, state, lat, lon) VALUES ('shimla', 'Shimla',"
                " 'Himachal Pradesh', 31.1, 77.17) RETURNING id"
            )  # fmt: skip
        ).scalar_one()
        start = day_bounds(DAY)[0]
        for h in range(-24, 72):
            hour = start + timedelta(hours=h)
            for pollutant, value in (("pm25", 40.0), ("pm10", 60.0), ("no2", 20.0),
                                     ("co2", 430.0)):  # fmt: skip
                conn.execute(
                    text(
                        "INSERT INTO model_air (district_id, lat, lon, hour, pollutant, value,"
                        " unit, model_run, is_forecast, fetched_at) VALUES (:d, 31.1, 77.2, :h,"
                        " :p, :v, :u, :h, :f, :h) ON CONFLICT DO NOTHING"
                    ),
                    {"d": shimla, "h": hour, "p": pollutant, "v": value,
                     "u": "ppm" if pollutant == "co2" else "ug/m3", "f": hour > NOW},
                )  # fmt: skip
        _seed_weather(conn, delhi, 26.0)
        _seed_weather(conn, shimla, 9.0)
    with Session(db_engine) as session:
        build_recent(session, days=1, now=NOW)
    return {"delhi": delhi, "shimla": shimla}
