from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.analysis.aqi import AqiResult
from app.analysis.summary import build_city_day, build_recent, city_aqi
from app.analysis.time import day_bounds
from app.models import DailyCitySummary, District, Reading, StationDayCompleteness
from tests.analysis.helpers import DAY

NOW = day_bounds(DAY)[1] + timedelta(hours=2)  # the day is complete


from tests.seed import seed_delhi as _seed  # noqa: E402


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
    assert row["stations_total"] == 4


def test_rebuild_is_idempotent(db_engine):
    with db_engine.begin() as conn:
        _seed(conn)
    with Session(db_engine) as session:
        build_recent(session, days=1, now=NOW - timedelta(hours=3))
        build_recent(session, days=1, now=NOW - timedelta(hours=3))
        assert session.scalar(select(func.count()).select_from(DailyCitySummary)) == 1


def test_partial_day_counts_only_finished_hours(db_engine):
    with db_engine.begin() as conn:
        did = _seed(conn)
    with Session(db_engine) as session:
        now = day_bounds(DAY)[0] + timedelta(hours=10, minutes=20)
        row = build_city_day(session, session.get(District, did), DAY, now)
    # 10 hours finished, the last 2 are still settling (data arrives late)
    assert row["is_partial_day"] and row["hours_covered"] == 8
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


def test_stations_without_any_data_are_not_counted(db_engine):
    with db_engine.begin() as conn:
        did = _seed(conn)
        conn.execute(
            text(
                "INSERT INTO stations (source, external_id, name, lat, lon, district_id,"
                " is_reference) VALUES ('openaq', 'new', 'Not collected yet', 28.6, 77.2, :d,"
                " true)"
            ),  # fmt: skip
            {"d": did},
        )
    with Session(db_engine) as session:
        row = build_city_day(session, session.get(District, did), DAY, NOW)
    assert row["stations_total"] == 4 and row["completeness_pct"] == 87.5


def test_official_figure_is_not_held_back_by_settling(db_engine):
    with db_engine.begin() as conn:
        did = _seed(conn)
    with Session(db_engine) as session:
        # 16:30 IST: the bulletin hour (16:00) is in the feed; OpenAQ hours still settling
        now = day_bounds(DAY)[0] + timedelta(hours=17, minutes=30)
        row = build_city_day(session, session.get(District, did), DAY, now)
    assert row["official_aqi"] == 310


def test_city_hours_series(db_engine):
    from app.analysis.summary import build_city_hours, floor_ist_hour
    from app.models import CityHourAqi

    with db_engine.begin() as conn:
        did = _seed(conn)
    with Session(db_engine) as session:
        n = build_city_hours(session, session.get(District, did), NOW)
        session.commit()
        rows = {r.hour: r for r in session.execute(select(CityHourAqi)).scalars()}
    assert n == len(rows) == 48
    bulletin = day_bounds(DAY)[0] + timedelta(hours=16)
    assert rows[bulletin].official_aqi == 310
    last_day_hour = day_bounds(DAY)[1] - timedelta(hours=1)
    assert rows[last_day_hour].measured_aqi is not None
    assert rows[last_day_hour].shadow_aqi is not None
    assert rows[last_day_hour].cams_aqi is not None  # 24 model hours -> running AQI
    assert floor_ist_hour(datetime(2026, 11, 8, 10, 10, tzinfo=UTC)) == datetime(
        2026, 11, 8, 9, 30, tzinfo=UTC
    )
