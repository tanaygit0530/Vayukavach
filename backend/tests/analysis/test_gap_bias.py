import numpy as np
import pandas as pd

from app.analysis.gap_bias import excluded_readings, hourly_missing_rate, missing_when_it_mattered
from tests.analysis.helpers import DAY, HOURS, readings


def _level():
    # clean mornings, very polluted night (hours 18-23 IST highest)
    return pd.Series(np.arange(24, dtype=float), index=HOURS)


def test_flags_gaps_clustered_in_polluted_hours():
    missing = pd.Series([0.0] * 18 + [0.5] * 6, index=HOURS)
    result = missing_when_it_mattered(_level(), missing)
    assert result.flagged
    assert (result.polluted_missing_pct, result.clean_missing_pct, result.diff_pp) == (
        50.0, 0.0, 50.0
    )  # fmt: skip
    assert result.polluted_hours == [h.to_pydatetime() for h in HOURS[18:]]


def test_even_gaps_are_not_flagged():
    missing = pd.Series([0.1] * 24, index=HOURS)
    result = missing_when_it_mattered(_level(), missing)
    assert not result.flagged and result.diff_pp == 0.0


def test_threshold_is_configurable():
    missing = pd.Series([0.0] * 18 + [0.15] * 6, index=HOURS)
    assert not missing_when_it_mattered(_level(), missing).flagged  # 15 pp < 20
    assert missing_when_it_mattered(_level(), missing, threshold_pp=10).flagged


def test_needs_enough_hours():
    assert missing_when_it_mattered(_level().head(11), pd.Series(0.0, index=HOURS[:11])) is None


def test_hourly_missing_rate_from_readings():
    df = readings({(1, "pm25"): [1.0] * 12 + [None] * 12, (2, "pm25"): [1.0] * 24})
    rate = hourly_missing_rate(df, DAY)
    assert list(rate[:12]) == [0.0] * 12 and list(rate[12:]) == [0.5] * 12


def test_excluded_and_near_limit_readings():
    df = readings({(1, "pm25"): [100.0] * 20 + ["x", 960.0, None, 100.0]})
    out = excluded_readings(df)
    assert len(out) == 2
    assert list(out["at_or_over_limit"]) == [True, False]
