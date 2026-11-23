from datetime import UTC, datetime, timedelta

import numpy as np
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.analysis.aqi import AqiResult
from app.analysis.summary import build_city_day, build_recent, city_aqi
from app.analysis.time import day_bounds, day_hours
from app.models import DailyCitySummary, District, Reading, StationDayCompleteness
from tests.analysis.helpers import DAY

NOW = day_bounds(DAY)[1] + timedelta(hours=2)  # the day is complete


def _seed(conn):
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
            "INSERT INTO stations (source, external_id, name, district_id) VALUES"
            " ('cpcb', 'S', 'S', :d) RETURNING id"
        ),  # fmt: skip
        {"d": did},
    ).scalar_one()
    hours = day_hours(DAY)
    level = np.linspace(100, 400, 24)  # pollution rises through the day
    rows = []
    for h_i, hour in enumerate(hours):
        conn.execute(
            text(
                "INSERT INTO model_air (district_id, lat, lon, hour, pollutant, value, unit,"
                " model_run, is_forecast, fetched_at) VALUES (:d, 28.6, 77.2, :h, 'pm25', :v,"
                " 'ug/m3', :h, false, :h)"
            ),  # fmt: skip
            {"d": did, "h": hour, "v": float(level[h_i])},
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


def test_city_day_summary_end_to_end(db_engine):
    with db_engine.begin() as conn:
        did = _seed(conn)
    with Session(db_engine) as session:
        before = session.scalar(select(func.count()).select_from(Reading))
        district = session.get(District, did)
        row = build_city_day(session, district, DAY, NOW)
        session.commit()
        after = session.scalar(select(func.count()).select_from(Reading))
        stored = session.execute(select(DailyCitySummary)).scalar_one()
        per_station = session.scalar(select(func.count()).select_from(StationDayCompleteness))

    assert before == after  # real readings are never touched
    assert not row["is_partial_day"] and row["hours_covered"] == 24
    # 2 of 4 stations silent 6 of 24 hours -> 12 / 96 station-hours missing per pollutant
    assert row["completeness_pct"] == 87.5
    assert row["stations_silent"] == 2
    assert row["city_silent_hours"] == 6  # 50% of stations silent in those hours
    # gaps fall exactly in the six most polluted hours
    assert row["gap_bias_flag"] is True
    assert row["gap_bias_level_source"] == "cams"
    assert row["polluted_missing_pct"] == 50.0 and row["clean_missing_pct"] == 0.0
    # official figure from CPCB sub-indices at the 4 PM bulletin hour
    assert row["official_aqi"] == 310 and row["official_stations"] == 1
    # measured drops the >999 value; shadow fills the silent hours (the worst ones)
    assert row["excluded_count"] == 1
    assert row["filled_hours"] == 2 * 6 * 3
    assert row["unfilled_hours"] == 0
    assert row["shadow_aqi"] >= row["measured_aqi"]
    assert row["shadow_aqi_low"] <= row["shadow_aqi"] <= row["shadow_aqi_high"]
    assert row["shadow_mae_pm25"] is not None and row["shadow_validation_n"] > 0
    assert stored.shadow_aqi == row["shadow_aqi"]
    assert per_station == 4 * 3


def test_rebuild_is_idempotent(db_engine):
    with db_engine.begin() as conn:
        _seed(conn)
    with Session(db_engine) as session:
        build_recent(session, days=1, now=NOW - timedelta(hours=2, minutes=1))
        build_recent(session, days=1, now=NOW - timedelta(hours=2, minutes=1))
        assert session.scalar(select(func.count()).select_from(DailyCitySummary)) == 1


def test_partial_day_counts_only_finished_hours(db_engine):
    with db_engine.begin() as conn:
        did = _seed(conn)
    with Session(db_engine) as session:
        now = day_bounds(DAY)[0] + timedelta(hours=10, minutes=20)
        row = build_city_day(session, session.get(District, did), DAY, now)
    assert row["is_partial_day"] and row["hours_covered"] == 10
    assert row["completeness_pct"] == 100.0


def test_city_aqi_uses_only_valid_stations():
    results = {
        1: AqiResult(300, "pm25", {}, True),
        2: AqiResult(200, "pm10", {}, True),
        3: AqiResult(450, "pm25", {}, False, "only 1 pollutant"),
    }
    city = city_aqi(results)
    assert (city.aqi, city.stations) == (250, 2)


def test_no_data_day_is_skipped(db_engine):
    with Session(db_engine) as session:
        session.add(District(slug="x", name="X", state="S", lat=1, lon=1))
        session.flush()
        before_day = datetime(2026, 11, 7, 18, 0, tzinfo=UTC)  # 23:30 IST, before DAY starts
        assert build_city_day(session, session.scalars(select(District)).one(), DAY,
                              before_day) is None  # fmt: skip
