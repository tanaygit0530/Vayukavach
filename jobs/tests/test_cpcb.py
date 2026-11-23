from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import District, Reading, Station
from collectors import cpcb
from tests.conftest import load

T0 = datetime(2026, 11, 23, 11, 5, tzinfo=UTC)
SNAPSHOT_HOUR = datetime(2026, 11, 23, 9, 30, tzinfo=UTC)  # hour 15:00-16:00 IST


def _raw():
    return load("cpcb_delhi.json")["records"]


def test_last_update_is_the_end_of_the_hour():
    # stamped 16:00 IST -> covers 15:00-16:00 IST -> hour starts 09:30 UTC
    assert cpcb.parse_last_update("23-11-2026 16:00:00") == SNAPSHOT_HOUR
    assert cpcb.parse_last_update("24-11-2026 00:00:00") == datetime(2026, 11, 23, 17, 30,
                                                                      tzinfo=UTC)  # fmt: skip


def test_parse_dedupes_repeated_records_across_pages():
    raw = _raw()
    records, bad = cpcb.parse_records(raw)
    assert bad == 0
    assert len(raw) == 20
    assert len(records) == len({(r["station"].strip(), r["pollutant_id"]) for r in raw})
    assert len(records) < len(raw)


def test_parse_maps_pollutants_and_values():
    records, _ = cpcb.parse_records(_raw())
    pols = {r.pollutant for r in records}
    assert pols <= {"pm25", "pm10", "no2", "so2", "co", "o3", "nh3"}
    assert "o3" in pols  # OZONE -> o3
    dtu_pm10 = next(r for r in records if r.station.startswith("DTU") and r.pollutant == "pm10")
    assert dtu_pm10.value == 212.0
    assert dtu_pm10.hour == SNAPSHOT_HOUR


def test_parse_handles_na_and_bad_rows():
    raw = [
        {**_raw()[0], "avg_value": "NA"},
        {**_raw()[1], "last_update": "not a date"},
        {**_raw()[2], "pollutant_id": "BENZENE"},
    ]
    records, bad = cpcb.parse_records(raw)
    assert len(records) == 1 and records[0].value is None
    assert bad == 2


def test_store_writes_stations_readings_and_maps_to_delhi(session, districts):
    records, _ = cpcb.parse_records(_raw())
    cpcb.store(session, records, districts, T0)
    session.commit()

    delhi_id = session.execute(select(District.id).where(District.slug == "delhi")).scalar_one()
    stations = session.execute(select(Station)).scalars().all()
    assert {s.district_id for s in stations} == {delhi_id}
    ok = session.execute(select(Reading).where(Reading.status == "ok")).scalars().all()
    assert len(ok) == len(records)
    assert {r.unit for r in ok} == {"aqi_subindex"}
    assert all(r.hour == SNAPSHOT_HOUR for r in ok)


def _counts(session):
    return dict(
        session.execute(select(Reading.status, func.count()).group_by(Reading.status)).all()
    )


def test_next_hour_without_a_station_creates_missing_rows(session, districts):
    records, _ = cpcb.parse_records(_raw())
    cpcb.store(session, records, districts, T0)

    # One hour later the feed has every station except DTU.
    later = [
        r.__class__(**{**r.__dict__, "hour": SNAPSHOT_HOUR + timedelta(hours=1)})
        for r in records
        if not r.station.startswith("DTU")
    ]
    cpcb.store(session, later, districts, T0 + timedelta(hours=1))
    session.commit()

    dtu_pollutants = {r.pollutant for r in records if r.station.startswith("DTU")}
    missing = session.execute(
        select(Reading.pollutant, Reading.value, Reading.reason)
        .join(Station)
        .where(Station.name.like("DTU%"), Reading.hour == SNAPSHOT_HOUR + timedelta(hours=1))
    ).all()
    assert {m.pollutant for m in missing} == dtu_pollutants
    assert all(m.value is None and m.reason == "not_in_feed" for m in missing)


def test_rerunning_same_snapshot_is_idempotent(session, districts):
    records, _ = cpcb.parse_records(_raw())
    cpcb.store(session, records, districts, T0)
    first = _counts(session)
    cpcb.store(session, records, districts, T0 + timedelta(minutes=5))
    assert _counts(session) == first
    assert "missing" not in first  # everything expected arrived


def test_missing_marker_never_overwrites_a_real_value(session, districts):
    records, _ = cpcb.parse_records(_raw())
    cpcb.store(session, records, districts, T0)
    na = [records[0].__class__(**{**records[0].__dict__, "value": None})]
    cpcb.store(session, na, districts, T0 + timedelta(minutes=5))
    session.commit()
    row = session.execute(
        select(Reading)
        .join(Station)
        .where(
            Station.name == records[0].station,
            Reading.pollutant == records[0].pollutant,
            Reading.hour == SNAPSHOT_HOUR,
        )
    ).scalar_one()
    assert row.status == "ok" and row.value == records[0].value


def test_late_value_replaces_missing_marker(session, districts):
    records, _ = cpcb.parse_records(_raw())
    first = records[0]
    cpcb.store(session, [first.__class__(**{**first.__dict__, "value": None})], districts, T0)
    cpcb.store(session, [first], districts, T0 + timedelta(minutes=30))
    session.commit()
    row = session.execute(select(Reading)).scalar_one()
    assert (row.status, row.value, row.reason) == ("ok", first.value, None)
