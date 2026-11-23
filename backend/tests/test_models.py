from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.testing import downgrade, migrate

HOUR = datetime(2026, 11, 8, 18, tzinfo=UTC)


def _station(conn) -> int:
    return conn.execute(
        text(
            "INSERT INTO stations (source, external_id, name) VALUES ('cpcb', 'S1', 'S1')"
            " RETURNING id"
        )
    ).scalar_one()


def _reading(conn, station_id, value, status, pollutant="pm25"):
    conn.execute(
        text(
            "INSERT INTO readings (station_id, hour, pollutant, value, unit, status, source,"
            " fetched_at) VALUES (:s, :h, :p, :v, 'ug/m3', :st, 'cpcb', now())"
        ),
        {"s": station_id, "h": HOUR, "p": pollutant, "v": value, "st": status},
    )


def test_all_tables_exist(db_engine):
    tables = set(inspect(db_engine).get_table_names())
    expected = {"stations", "readings", "model_air", "weather", "weather_daily", "districts"}
    assert expected | {"fetch_log"} <= tables


def test_missing_reading_is_stored_as_null_row(conn):
    sid = _station(conn)
    _reading(conn, sid, None, "missing")
    row = conn.execute(text("SELECT value, status FROM readings")).one()
    assert row == (None, "missing")


def test_missing_status_with_a_value_is_rejected(conn):
    sid = _station(conn)
    with pytest.raises(IntegrityError):
        _reading(conn, sid, 0.0, "missing")


def test_ok_status_without_value_is_rejected(conn):
    sid = _station(conn)
    with pytest.raises(IntegrityError):
        _reading(conn, sid, None, "ok")


def test_one_row_per_station_hour_pollutant(conn):
    sid = _station(conn)
    _reading(conn, sid, 120.0, "ok")
    with pytest.raises(IntegrityError):
        _reading(conn, sid, 130.0, "ok")


def test_unknown_pollutant_is_rejected(conn):
    sid = _station(conn)
    with pytest.raises(IntegrityError):
        _reading(conn, sid, 1.0, "ok", pollutant="benzene")


def test_migration_downgrades_and_upgrades(db_url, db_engine):
    downgrade(db_url, "base")
    assert "readings" not in inspect(db_engine).get_table_names()
    migrate(db_url)
    assert "readings" in inspect(db_engine).get_table_names()
