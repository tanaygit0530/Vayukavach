import pytest

from app.analysis.heat import (
    HeatHour,
    assess_hour,
    heat_index_c,
    level_for,
    safe_windows,
    tips_for,
    wet_bulb_c,
    worst_level,
)


def f_to_c(f):
    return (f - 32) * 5 / 9


@pytest.mark.parametrize(
    ("temp_f", "rh", "hi_f"),
    [
        (90, 70, 106),  # NWS heat index chart
        (96, 50, 108),
        (100, 40, 109),
        (104, 55, 137),
        (86, 90, 105),
    ],
)
def test_heat_index_matches_nws_table(temp_f, rh, hi_f):
    assert heat_index_c(f_to_c(temp_f), rh) == pytest.approx(f_to_c(hi_f), abs=0.8)


def test_rothfusz_regression_arithmetic():
    # 90 degF, 40 %: the 9 regression terms sum to 90.67 degF (worked by hand)
    assert heat_index_c(f_to_c(90), 40) == pytest.approx(f_to_c(90.67), abs=0.02)


def test_heat_index_below_80f_uses_simple_formula():
    # 70 degF, 50 %: simple formula -> about 69.3 degF
    assert heat_index_c(f_to_c(70), 50) == pytest.approx(f_to_c(69.3), abs=0.3)


def test_low_humidity_adjustment_lowers_heat_index():
    t = f_to_c(100)
    assert heat_index_c(t, 10) < heat_index_c(t, 13.0001) + 0.01


@pytest.mark.parametrize(
    ("temp", "rh", "psychrometric", "stull"),
    [
        (20.0, 50.0, 13.88, 13.70),
        (30.0, 70.0, 25.57, 25.60),
        (35.0, 60.0, 28.28, 28.49),
        (45.0, 30.0, 28.95, 29.69),
    ],
)
def test_stull_wet_bulb(temp, rh, psychrometric, stull):
    # reference: iterative psychrometric solution at 1013.25 hPa; Stull's stated error < 1 degC
    assert wet_bulb_c(temp, rh) == pytest.approx(psychrometric, abs=1.0)
    assert wet_bulb_c(temp, rh) == pytest.approx(stull, abs=0.01)


def test_wet_bulb_never_above_air_temperature():
    for t in range(10, 48, 4):
        for rh in range(10, 99, 10):
            assert wet_bulb_c(t, rh) <= t + 0.5


@pytest.mark.parametrize(
    ("hi", "wb", "level"),
    [(28, 20, "normal"), (33, 20, "caution"), (30, 26.5, "caution"), (42, 20, "danger"),
     (35, 29, "danger"), (55, 20, "extreme"), (40, 31.5, "extreme"), (None, None, None)],
)  # fmt: skip
def test_levels(hi, wb, level):
    assert level_for(hi, wb) == level


def _day(levels):
    return [HeatHour(None, h, 30, 50, 30, 30, 20, lvl) for h, lvl in enumerate(levels)]


def test_safe_windows_inside_work_day():
    levels = ["normal"] * 11 + ["danger"] * 5 + ["normal"] * 8  # danger 11:00-16:00
    assert safe_windows(_day(levels)) == [(6, 11), (16, 19)]


def test_missing_hours_are_not_safe():
    hours = [h for h in _day(["normal"] * 24) if h.local_hour != 9]
    assert safe_windows(hours) == [(6, 9), (10, 19)]


def test_assess_hour_and_worst_level():
    hot = assess_hour(None, 14, 38.0, 60.0)
    assert hot.level in {"danger", "extreme"} and hot.wet_bulb > 30
    assert assess_hour(None, 14, None, 60.0).level is None
    assert worst_level([assess_hour(None, 8, 25.0, 40.0), hot]) == hot.level


def test_tips_accumulate_and_cite_108():
    assert len(tips_for("normal")) == 1
    assert len(tips_for("extreme")) > len(tips_for("danger")) > len(tips_for("caution"))
    assert any("108" in t for t in tips_for("extreme"))
