from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from app.analysis.aqi import RUNNING, station_aqi
from app.analysis.hourly import running_city_aqi, running_sub_indices
from app.analysis.summary import city_aqi

IDX = pd.date_range("2026-11-07T18:30Z", periods=48, freq="1h")


def _frames(seed=0, holes=0.15):
    rng = np.random.default_rng(seed)
    out = {}
    for pollutant, scale in (("pm25", 150), ("pm10", 250), ("no2", 60), ("co", 1.5), ("o3", 40)):
        data = rng.uniform(0.3, 1.7, size=(48, 5)) * scale
        data[rng.random((48, 5)) < holes] = np.nan
        out[pollutant] = pd.DataFrame(data, index=IDX, columns=[1, 2, 3, 4, 5])
    return out


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_vectorised_matches_scalar_for_every_hour(seed):
    frames = _frames(seed)
    fast = running_city_aqi(frames)
    for h in (23, 30, 40, 47):
        end = IDX[h] + timedelta(hours=1)
        results = {
            s: station_aqi({p: f[s] for p, f in frames.items()}, end, RUNNING)
            for s in frames["pm25"].columns
        }
        slow = city_aqi(results)
        assert fast.loc[IDX[h], "aqi"] == slow.aqi, h
        assert fast.loc[IDX[h], "stations"] == slow.stations


def test_first_hours_have_no_aqi_until_16_hours_of_data():
    fast = running_city_aqi(_frames(holes=0))
    assert fast.iloc[:15]["aqi"].isna().all()
    assert fast.iloc[15:]["aqi"].notna().all()


def test_gaps_in_the_index_count_as_missing_hours():
    frame = pd.DataFrame({1: [100.0] * 20}, index=IDX[:20]).drop(IDX[5:10])
    subs = running_sub_indices("pm25", frame)
    assert len(subs) == 20  # reindexed to every hour
    assert subs.iloc[-1].isna().all()  # only 15 valid hours in the window


def test_empty_input():
    assert running_city_aqi({}).empty
