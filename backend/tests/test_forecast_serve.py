"""The nightly job end to end on a synthetic year: backtest gate, model rows, forecast rows."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.time import day_bounds
from app.forecast import serve
from app.models import (
    AqiForecastDaily,
    CityDailyAqi,
    District,
    DistrictDailyFeatures,
    ForecastModel,
    ModelAir,
)
from tests.test_forecast_model import DAYS, START, synthetic_tables

TODAY = START + timedelta(days=DAYS - 12)  # features run 11 days past "today"
NOW = day_bounds(TODAY)[0] + timedelta(hours=3)  # 03:00 IST, as the nightly job runs


@pytest.fixture(scope="module")
def data():
    return synthetic_tables()


@pytest.fixture
def session(db_engine, data):
    target, feats = data
    with Session(db_engine) as s:
        for d_id, slug in ((1, "alpha"), (2, "beta"), (3, "nodata")):
            s.add(District(id=d_id, slug=slug, name=slug.title(), state="Test", lat=28.6, lon=77.2))
        s.flush()
        fetched = datetime(2026, 1, 1, tzinfo=UTC)
        s.add_all(
            DistrictDailyFeatures(**r, is_forecast=r["date"] >= TODAY, fetched_at=fetched)
            for r in feats.to_dict("records")
        )
        past = target[target["date"] < TODAY]
        s.add_all(
            CityDailyAqi(
                district_id=int(r["district_id"]),
                date=r["date"],
                aqi=int(r["aqi"]),
                stations=4,
                pm25=r["pm25"],
                pm10=r["pm10"],
                no2=r["no2"],
                so2=r["so2"],
                co=r["co"],
                o3=r["o3"],
                source="openaq",
                computed_at=fetched,
            )  # fmt: skip
            for r in past.to_dict("records")
        )
        # hourly CAMS for the range around the daily value (district 1 only)
        start = day_bounds(TODAY)[0] - timedelta(hours=24)
        for h in range(24 * 6):
            hour = start + timedelta(hours=h)
            shape = 1 + 0.4 * np.sin(h / 24 * 2 * np.pi)
            for pol, base in (("pm25", 60.0), ("pm10", 100.0), ("no2", 30.0)):  # AQI needs 3
                s.add(ModelAir(district_id=1, lat=28.6, lon=77.2, hour=hour, pollutant=pol,
                               value=base * shape, unit="µg/m³", model_run=start, fetched_at=start,
                               is_forecast=hour > NOW))  # fmt: skip
        s.commit()
        yield s


def test_nightly_writes_models_and_ten_day_forecasts(session):
    r = serve.run_nightly(session, now=NOW, weeks=6)
    assert r.version.startswith(TODAY.isoformat())
    kinds = session.execute(select(ForecastModel.kind, ForecastModel.beats_baseline)).all()
    assert {k for k, _ in kinds} == {"bias", "outlook"}

    rows = (
        session.execute(select(AqiForecastDaily).where(AqiForecastDaily.district_id == 1))
        .scalars()
        .all()
    )
    by_lead = {x.lead_days: x for x in rows}
    assert set(range(1, 6)) <= set(by_lead)  # days 1-5 always (corrected or raw CAMS)
    first = by_lead[1]
    assert first.issue_date == TODAY and first.target_date == TODAY
    assert first.method in ("cams_corrected", "cams_raw")
    assert first.low is not None and first.low <= first.median <= first.high  # hourly shape
    if r.summary["outlook_beats_baseline"]:
        assert {x.method for x in rows if x.lead_days > 5} == {"outlook"}
    else:
        assert all(x.lead_days <= 5 for x in rows)
    # district 2 has no hourly CAMS: a value but no range
    d2 = session.execute(
        select(AqiForecastDaily).where(
            AqiForecastDaily.district_id == 2, AqiForecastDaily.lead_days == 1
        )
    ).scalar_one()
    assert d2.median is not None and d2.low is None
    # a district with no data gets nothing, never zeros
    assert not session.execute(
        select(AqiForecastDaily).where(AqiForecastDaily.district_id == 3)
    ).first()
    assert r.rows_written == len(session.execute(select(AqiForecastDaily)).all())
    # re-running the same night updates rows instead of duplicating them
    again = serve.run_nightly(session, now=NOW, weeks=6)
    assert (
        again.rows_written == r.rows_written == len(session.execute(select(AqiForecastDaily)).all())
    )


def test_empty_database_has_no_frame(db_engine):
    with Session(db_engine) as s:
        assert serve.load_frame(s).empty
