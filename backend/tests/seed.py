"""Shared synthetic data: Delhi on Diwali 2026 (stations go silent as pollution peaks)."""

from datetime import timedelta

import numpy as np
from sqlalchemy import text

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
