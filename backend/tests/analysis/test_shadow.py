import numpy as np
import pandas as pd
import pytest

from app.analysis.shadow import (
    Neighbour,
    fill_missing,
    haversine_km,
    idw_estimate,
    validate_holdout,
)


def test_idw_weights_closer_stations_more():
    est = idw_estimate([Neighbour(1.0, 100.0), Neighbour(2.0, 200.0)])
    # weights 1 and 1/4 -> (100 + 50) / 1.25 = 120
    assert est == pytest.approx(120.0)


def test_idw_ignores_stations_beyond_radius():
    assert idw_estimate([Neighbour(16.0, 100.0)]) is None
    assert idw_estimate([Neighbour(16.0, 100.0), Neighbour(5.0, 80.0)]) == pytest.approx(80.0)


def test_model_difference_shifts_neighbours():
    # target's model value is 20 higher than the neighbour's -> estimate 20 higher
    assert idw_estimate([Neighbour(3.0, 100.0, model=80.0)], target_model=100.0) == 120.0
    # missing model data -> no shift
    assert idw_estimate([Neighbour(3.0, 100.0, model=None)], target_model=100.0) == 100.0


def test_estimate_never_negative():
    assert idw_estimate([Neighbour(1.0, 5.0, model=50.0)], target_model=0.0) == 0.0


def test_haversine_known_distance():
    # Connaught Place to India Gate, about 2.4 km
    assert haversine_km(28.6315, 77.2167, 28.6129, 77.2295) == pytest.approx(2.4, abs=0.2)


COORDS = {1: (28.60, 77.20), 2: (28.61, 77.20), 3: (28.60, 77.21), 4: (29.50, 77.20)}


def _frame():
    idx = pd.date_range("2026-11-08T18:30Z", periods=4, freq="1h")
    return pd.DataFrame(
        {1: [100.0, np.nan, 120.0, np.nan], 2: [110.0, 115.0, np.nan, np.nan],
         3: [90.0, 95.0, 100.0, np.nan], 4: [np.nan, 40.0, 40.0, 40.0]},
        index=idx,
    )  # fmt: skip


def test_fill_only_missing_cells_and_never_touch_real_values():
    values = _frame()
    filled, mask = fill_missing(values, COORDS)
    real = values.notna()
    assert filled.where(real).equals(values.where(real))
    assert mask.iloc[1][1] and mask.iloc[2][2]
    assert not mask[real].any().any()


def test_isolated_station_stays_missing():
    filled, mask = fill_missing(_frame(), COORDS)
    assert np.isnan(filled.iloc[0][4]) and not mask.iloc[0][4]  # station 4 is ~100 km away
    assert np.isnan(filled.iloc[3][1])  # only far station 4 reported that hour


def test_holdout_validation_reports_error():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2026-11-08T18:30Z", periods=48, freq="1h")
    base = 150 + 50 * np.sin(np.arange(48) / 6)
    coords = {s: (28.60 + 0.01 * s, 77.20) for s in range(6)}
    values = pd.DataFrame({s: base + rng.normal(0, 5, 48) for s in coords}, index=idx)
    result = validate_holdout(values, coords, fraction=0.1)
    assert result.n_held_out == 29 and result.n == 29
    assert 0 < result.mae < 15  # neighbours share the signal, noise sd 5
    assert validate_holdout(values.iloc[0:0], coords).mae is None
