from datetime import timedelta

import pandas as pd

from app.analysis.validate_cpcb import compare, link_stations, normalise_name, report
from tests.analysis.helpers import HOURS


def test_names_link_ignoring_case_and_spacing():
    assert normalise_name("Dwarka-Sector 8, Delhi - DPCC ") == "dwarka-sector 8, delhi - dpcc"
    cpcb = pd.DataFrame(
        {"id": [1, 2, 3], "name": ["R K Puram, Delhi - DPCC ", "Other A", "Far B"],
         "lat": [28.56, 28.70, 20.0], "lon": [77.18, 77.10, 77.0]}
    )  # fmt: skip
    openaq = pd.DataFrame(
        {"id": [10, 11], "name": ["R K Puram,  Delhi - DPCC", "Different name"],
         "lat": [28.56, 28.7001], "lon": [77.18, 77.1001]}
    )  # fmt: skip
    assert link_stations(cpcb, openaq) == {1: 10, 2: 11}  # 2 by distance, 3 unmatched


def test_compare_matches_when_concentrations_agree():
    conc = pd.DataFrame(
        {"station_id": 10, "hour": HOURS, "pollutant": "pm25", "value": 150.0}
    )  # 24 h at 150 ug/m3 -> sub-index 323
    cpcb = pd.DataFrame(
        {"station_id": [1], "station": ["S"], "hour": [HOURS[-1]], "pollutant": ["pm25"],
         "value": [323.0]}
    )  # fmt: skip
    result = compare(cpcb, conc, {1: 10})
    assert result.rows["diff"].tolist() == [0]
    per = result.by_pollutant()
    assert per.loc["pm25", "mae_points"] == 0 and per.loc["pm25", "within_5"] == 100
    assert "pm25" in report(result)


def test_compare_skips_unlinked_or_thin_data():
    conc = pd.DataFrame(
        {"station_id": 10, "hour": HOURS[:10], "pollutant": "pm25", "value": 150.0}
    )  # only 10 hours: no valid 24-h mean
    cpcb = pd.DataFrame(
        {"station_id": [1, 2], "station": ["S", "T"], "hour": [HOURS[9]] * 2,
         "pollutant": ["pm25"] * 2, "value": [323.0] * 2}
    )  # fmt: skip
    result = compare(cpcb, conc, {1: 10})
    assert result.rows.empty
    assert "No overlapping" in report(result)


def test_window_ends_with_the_reported_hour():
    values = [50.0] * 23 + [500.0]  # the reported hour itself is high
    conc = pd.DataFrame({"station_id": 10, "hour": HOURS, "pollutant": "pm25", "value": values})
    cpcb = pd.DataFrame(
        {"station_id": [1], "station": ["S"], "hour": [HOURS[-1]], "pollutant": ["pm25"],
         "value": [0.0]}
    )  # fmt: skip
    ours = compare(cpcb, conc, {1: 10}).rows["ours"].iloc[0]
    # mean = (23*50 + 500)/24 = 68.75 -> includes the last hour
    assert ours == round((200 - 101) / (90 - 61) * (68.75 - 61) + 101)
    assert HOURS[-1] + timedelta(hours=1) > HOURS[-1]
