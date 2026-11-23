from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.analysis.aqi import (
    DAILY,
    aqi_from_concentrations,
    category,
    station_aqi,
    sub_index,
    window_average,
)
from app.analysis.aqi_breakpoints import AQI_BANDS, CONCENTRATION_BANDS


@pytest.mark.parametrize(
    ("pollutant", "conc", "expected"),
    [
        ("pm25", 0, 0),
        ("pm25", 30, 50),
        ("pm25", 60, 100),
        ("pm25", 150, 323),  # worked example: 99/129 * 29 + 301 = 323.3
        ("pm25", 250, 400),
        ("pm25", 251, 401),
        ("pm25", 380, 500),
        ("pm10", 100, 100),
        ("pm10", 300, 250),  # (300-201)/(350-251)*(300-251)+201 = 249.5 -> 250
        ("no2", 180, 200),
        ("so2", 40, 50),
        ("o3", 168, 200),
        ("nh3", 400, 100),
        ("co", 1.5, 73),  # 49/0.9 * 0.4 + 51 = 72.8
        ("co", 10, 200),
    ],
)
def test_sub_index_hand_calculated(pollutant, conc, expected):
    assert round(sub_index(pollutant, conc)) == expected


def test_band_edges_map_to_band_edges():
    for pollutant, bands in CONCENTRATION_BANDS.items():
        for (b_lo, b_hi), (i_lo, i_hi) in zip(bands, AQI_BANDS, strict=True):
            assert sub_index(pollutant, b_lo) == pytest.approx(i_lo), pollutant
            assert sub_index(pollutant, b_hi) == pytest.approx(i_hi), pollutant


def test_value_in_gap_between_bands_takes_band_floor():
    assert sub_index("pm25", 30.5) == pytest.approx(51)


def test_above_scale_is_capped_at_500():
    assert sub_index("pm25", 1200) == 500
    assert sub_index("pm10", 999) == 500


@pytest.mark.parametrize("bad", [None, float("nan"), -1.0])
def test_no_valid_value_gives_none(bad):
    assert sub_index("pm25", bad) is None


def test_sub_index_is_monotonic():
    for pollutant, bands in CONCENTRATION_BANDS.items():
        top = bands[-1][1]
        xs = np.linspace(0, top, 400)
        ys = [sub_index(pollutant, x) for x in xs]
        assert all(b >= a - 1e-9 for a, b in zip(ys, ys[1:], strict=False)), pollutant


@pytest.mark.parametrize(
    ("aqi", "name"),
    [(0, "Good"), (50, "Good"), (51, "Satisfactory"), (100, "Satisfactory"), (101, "Moderate"),
     (200, "Moderate"), (201, "Poor"), (301, "Very poor"), (400, "Very poor"), (401, "Severe"),
     (500, "Severe")],
)  # fmt: skip
def test_category_boundaries(aqi, name):
    assert category(aqi)[0] == name


def test_aqi_is_highest_sub_index_and_names_pollutant():
    result = aqi_from_concentrations({"pm25": 150, "pm10": 200, "no2": 50, "co": None})
    assert result.valid
    assert (result.aqi, result.main_pollutant) == (323, "pm25")
    assert result.sub_indices == {"pm25": 323, "pm10": 167, "no2": 62}
    assert result.category == ("Very poor", "verypoor")


def test_aqi_needs_three_pollutants():
    result = aqi_from_concentrations({"pm25": 150, "no2": 50})
    assert not result.valid and "3" in result.reason
    assert result.aqi == 323  # still reported, but flagged


def test_aqi_needs_pm():
    result = aqi_from_concentrations({"no2": 50, "so2": 20, "o3": 40})
    assert not result.valid and "PM" in result.reason


def test_aqi_with_nothing():
    result = aqi_from_concentrations({"pm25": None})
    assert result.aqi is None and not result.valid


# ---------------------------------------------------------------- averaging

END = datetime(2026, 11, 9, 18, 30, tzinfo=UTC)  # 00:00 IST


def _hours(values, end=END):
    idx = pd.date_range(end - timedelta(hours=len(values)), periods=len(values), freq="1h")
    return pd.Series(values, index=idx, dtype=float)


def test_24h_average_needs_16_hours():
    full = _hours([100.0] * 16 + [np.nan] * 8)
    assert window_average(full, "pm25", END) == 100.0
    short = _hours([100.0] * 15 + [np.nan] * 9)
    assert window_average(short, "pm25", END) is None


def test_24h_average_ignores_hours_outside_window_and_negatives():
    values = [500.0] * 5 + [100.0] * 23 + [-1.0]  # 29 hours; first 5 are too old
    assert window_average(_hours(values), "pm25", END) == 100.0


def test_8h_running_mode_is_the_last_8_hours():
    values = [10.0] * 8 + [90.0] * 8 + [20.0] * 8  # earlier peak, last 8 h low
    assert window_average(_hours(values), "o3", END) == pytest.approx(20.0)


def test_8h_daily_mode_is_the_max_running_mean():
    values = [10.0] * 8 + [90.0] * 8 + [20.0] * 8
    assert window_average(_hours(values), "o3", END, mode=DAILY) == pytest.approx(90.0)


def test_8h_window_needs_6_hours():
    values = [50.0] * 19 + [np.nan] * 3 + [50.0] * 2  # only 2 valid in the last 8
    assert window_average(_hours(values), "co", END) is None
    assert window_average(_hours([np.nan] * 19 + [50.0] * 5), "co", END, mode=DAILY) is None


def test_station_aqi_end_to_end():
    hourly = {
        "pm25": _hours([150.0] * 24),
        "pm10": _hours([200.0] * 24),
        "no2": _hours([50.0] * 24),
        "co": _hours([1.5] * 24),
    }
    result = station_aqi(hourly, END)
    assert result.valid and result.aqi == 323 and result.sub_indices["co"] == 73
