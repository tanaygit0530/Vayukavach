from datetime import timedelta

import pandas as pd

from app.analysis.completeness import (
    longest_run,
    overall_pct,
    silence_report,
    silent_matrix,
    station_day_completeness,
)
from app.analysis.time import day_bounds, day_hours
from tests.analysis.helpers import DAY, HOURS, readings


def test_ist_day_has_24_hours_on_the_half_hour():
    assert len(HOURS) == 24
    assert HOURS[0].hour == 18 and HOURS[0].minute == 30  # 00:00 IST = 18:30 UTC day before


def test_today_counts_only_finished_hours():
    start, _ = day_bounds(DAY)
    assert len(day_hours(DAY, now=start + timedelta(hours=5, minutes=10))) == 5


def test_station_day_counts_received_excluded_and_gaps():
    values = [100.0] * 10 + [None] * 4 + ["-"] * 2 + ["x"] * 2 + [100.0] * 6
    df = station_day_completeness(readings({(1, "pm25"): values}), DAY)
    row = df.iloc[0]
    assert row.expected == 24
    assert row.received == 18  # 16 ok + 2 excluded (a value arrived)
    assert row.excluded == 2
    assert row.pct == 75.0
    assert row.longest_gap_hours == 6  # 4 missing rows + 2 hours with no row


def test_overall_pct():
    df = station_day_completeness(
        readings({(1, "pm25"): [1.0] * 24, (2, "pm25"): [1.0] * 12 + [None] * 12}), DAY
    )
    assert overall_pct(df) == 75.0
    assert overall_pct(df.iloc[0:0]) is None


def test_longest_run():
    assert longest_run(pd.Series([True, True, False, True, True, True])) == 3
    assert longest_run(pd.Series([], dtype=bool)) == 0


def test_station_silent_only_when_all_its_pollutants_are_missing():
    df = readings(
        {
            (1, "pm25"): [None] * 5 + [1.0] * 19,
            (1, "no2"): [1.0] * 24,  # still reporting NO2 -> not silent
            (2, "pm25"): [1.0] * 10 + [None] * 3 + [1.0] * 11,
        }
    )
    report = silence_report(silent_matrix(df, DAY))
    assert list(report.silent_stations) == [2]
    first, last = report.silent_stations[2][0]
    assert (first, last) == (HOURS[10], HOURS[12])


def test_two_hour_silence_is_not_flagged():
    df = readings({(1, "pm25"): [1.0] * 10 + [None] * 2 + [1.0] * 12})
    assert silence_report(silent_matrix(df, DAY)).silent_stations == {}


def test_city_hours_with_quarter_of_stations_silent():
    spec = {(s, "pm25"): [1.0] * 24 for s in range(1, 9)}
    spec[(1, "pm25")] = [1.0] * 20 + [None] * 4
    spec[(2, "pm25")] = [1.0] * 20 + [None] * 4  # 2 of 8 = 25% silent in hours 20-23
    spec[(3, "pm25")] = [None] + [1.0] * 23  # 1 of 8 in hour 0: not flagged
    report = silence_report(silent_matrix(readings(spec), DAY))
    assert report.city_silent_hours == [h.to_pydatetime() for h in HOURS[20:]]
    assert report.max_share_silent == 0.25
