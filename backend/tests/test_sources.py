import csv
from datetime import date

import pytest

from app.services.sources import normalise
from app.sources import STUDIES, check_sums, read_rows


def test_normalise_always_sums_to_exactly_100():
    out = normalise({"transport": 13.0, "household_fuel": 24.3, "outside_city": 62.6})  # 99.9
    assert round(sum(out.values()), 1) == 100.0
    assert out["outside_city"] == 62.7  # remainder on the largest
    assert normalise({}) == {}


def test_seed_csv_is_valid_and_sums_to_100():
    rows = read_rows(STUDIES, daily=False)
    cities = {r["city"] for r in rows}
    assert {"lucknow", "kolkata", "hyderabad", "shimla", "mumbai"} <= cities
    check_sums(rows)
    assert all(r["source_url"] and r["source_year"] == 2018 for r in rows)


def test_check_sums_rejects_incomplete_sets():
    rows = [{"city": "x", "date": None, "share_pct": 60.0}, {"city": "x", "date": None,
            "share_pct": 30.0}]  # fmt: skip
    with pytest.raises(ValueError, match="sum to 100"):
        check_sums(rows)


def test_unknown_sector_is_rejected(tmp_path):
    p = tmp_path / "bad.csv"
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["city", "sector", "share_pct", "source_name", "source_url", "source_year"])
        w.writerow(["delhi", "aliens", 100, "x", "", 2020])
    with pytest.raises(ValueError, match="unknown sector"):
        read_rows(p, daily=False)


def test_daily_rows_need_a_date(tmp_path):
    p = tmp_path / "daily.csv"
    p.write_text("date,sector,share_pct,source_name,source_url\n2026-11-24,transport,100,DSS,\n")
    assert read_rows(p, daily=True)[0]["date"] == date(2026, 11, 24)
