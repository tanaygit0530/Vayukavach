from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.forecast.model import (
    BiasModel,
    OutlookModel,
    backtest,
    build_frame,
    festival_flag,
    outlook_rows,
    report_markdown,
    stubble_flag,
    summary,
)

START = date(2025, 6, 1)
DAYS = 420


def synthetic(seed=0):
    return build_frame(*synthetic_tables(seed))


def synthetic_tables(seed=0):
    """CAMS reads 30% low and misses a wind effect; AQI has a smooth season + persistence.
    Returns (city daily targets, district daily features)."""
    rng = np.random.default_rng(seed)
    feats, targets = [], []
    for d_id in (1, 2):
        level = 0.0
        for i in range(DAYS):
            day = START + timedelta(days=i)
            season = 90 + 70 * np.cos(2 * np.pi * (day.timetuple().tm_yday - 15) / 365)
            level = 0.7 * level + rng.normal(0, 12)
            wind = rng.uniform(2, 15)
            true_pm25 = max(5.0, season + level - 3 * wind + (20 if d_id == 2 else 0))
            cams = true_pm25 * 0.7 + rng.normal(0, 6)
            feats.append(
                {
                    "district_id": d_id,
                    "date": day,
                    "cams_pm25": cams,
                    "cams_pm10": cams * 1.6,
                    "cams_no2": 30.0,
                    "cams_so2": 10.0,
                    "cams_co": 0.8,
                    "cams_o3": 40.0,
                    "temperature_mean": 25.0,
                    "humidity_mean": 55.0,
                    "wind_mean": wind,
                    "precipitation_sum": 0.0,
                    "blh_mean": 600.0,
                }
            )
            targets.append(
                {
                    "district_id": d_id,
                    "date": day,
                    "pm25": true_pm25,
                    "pm10": true_pm25 * 1.7,
                    "no2": 30.0,
                    "so2": 10.0,
                    "co": 0.8,
                    "o3": 40.0,
                }
            )
    t = pd.DataFrame(targets)
    from app.forecast.model import aqi_of

    t["aqi"] = [aqi_of(r) for r in t.to_dict("records")]
    return t, pd.DataFrame(feats)


@pytest.fixture(scope="module")
def frame():
    return synthetic()


def test_flags():
    assert festival_flag(date(2026, 11, 8)) == 1 and festival_flag(date(2026, 11, 6)) == 1
    assert festival_flag(date(2026, 11, 12)) == 0
    assert stubble_flag(date(2026, 9, 15)) == 1 and stubble_flag(date(2026, 9, 14)) == 0
    assert stubble_flag(date(2026, 12, 1)) == 0


def test_bias_correction_beats_raw_cams(frame):
    issue = date(2026, 4, 1)
    visible = frame.assign(
        pm25=frame["pm25"].where(frame["date"] < issue),
        pm10=frame["pm10"].where(frame["date"] < issue),
    )
    model = BiasModel().fit(frame[frame["date"] < issue])
    corr = model.corrected_values(visible, issue)
    assert set(corr["lead"]) == {1, 2, 3, 4, 5} and len(corr) == 10
    truth = frame.set_index(["district_id", "date"])["aqi"]
    keys = list(zip(corr["district_id"], corr["target_date"], strict=True))
    cams = frame.set_index(["district_id", "date"])["cams_aqi"].reindex(keys).to_numpy()
    y = truth.reindex(keys).to_numpy()
    assert np.nanmean(np.abs(corr["corrected_aqi"].astype(float) - y)) < np.nanmean(
        np.abs(cams - y)
    )


def test_bias_rows_lag_is_the_day_before_the_issue(frame):
    from app.forecast.model import bias_rows

    rows = bias_rows(frame, "pm25", leads=[3])
    r = rows[(rows["district_id"] == 1) & (rows["target_date"] == date(2026, 1, 10))].iloc[0]
    issue = date(2026, 1, 8)
    assert r.issue == issue
    expected = frame[(frame.district_id == 1) & (frame.date == issue - timedelta(days=1))]["pm25"]
    assert r.lag1 == pytest.approx(expected.iloc[0])


def test_outlook_rows_use_only_the_past(frame):
    t = date(2026, 1, 15)
    rows = outlook_rows(frame, issue_dates=[t], leads=[6])
    assert len(rows) == 2
    r = rows.iloc[0]
    assert r.target_date == t + timedelta(days=5)
    truth_yesterday = frame[
        (frame.district_id == r.district_id) & (frame.date == t - timedelta(days=1))
    ]["aqi"].iloc[0]
    assert r.lag1 == truth_yesterday


def test_outlook_quantiles_are_ordered(frame):
    rows = outlook_rows(frame[frame["date"] < date(2026, 3, 1)])
    model = OutlookModel().fit(rows)
    pred = model.predict(rows.head(50))
    assert (pred["low"] <= pred["mid"]).all() and (pred["mid"] <= pred["high"]).all()


def test_backtest_table_and_verdict(frame):
    bt = backtest(frame, end=START + timedelta(days=DAYS - 1), weeks=10, min_train_days=150)
    assert set(bt.table["day"]) == set(range(1, 11))
    early = bt.table[bt.table["day"] <= 5]
    assert set(early["method"]) == {"cams_corrected", "cams_raw", "persistence"}
    s = summary(bt)
    assert s["bias_beats_baseline"] is True
    assert 0 <= s["coverage_80"] <= 1
    md = report_markdown(bt, s)
    assert "| Day |" in md and "upper bound" in md


def test_centred_range_keeps_spread_around_the_model_value():
    from app.forecast.serve import centred_range

    assert centred_range((240.0, 300.0, 270.0), 310) == (280, 340)
    assert centred_range((10.0, 30.0, 20.0), 5) == (0, 15)  # clipped at 0
    assert centred_range(None, 300) is None and centred_range((1.0, 2.0, 1.5), None) is None
