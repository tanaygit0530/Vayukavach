"""Data-gap reports for journalists and researchers (neutral wording: completeness)."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analysis.completeness import silence_report, silent_matrix
from app.analysis.gap_bias import excluded_readings
from app.analysis.summary import load_readings, load_reference_stations
from app.analysis.time import day_bounds
from app.models import District
from app.services.air import latest_summary


def gap_report(session: Session, district: District, day: date, now: datetime) -> dict:
    coords = load_reference_stations(session, district.id)
    start, end = day_bounds(day)
    readings = load_readings(session, list(coords), start, min(end, now))
    names = dict(
        session.execute(
            text("SELECT id, name FROM stations WHERE id = ANY(:ids)"), {"ids": list(coords)}
        ).all()
    )
    silence = silence_report(silent_matrix(readings, day, now)) if not readings.empty else None
    per_station = (
        session.execute(
            text(
                "SELECT c.station_id, s.name, c.pollutant, c.expected, c.received, c.excluded,"
                " c.pct, c.longest_gap_hours FROM station_day_completeness c"
                " JOIN stations s ON s.id = c.station_id"
                " WHERE s.district_id = :d AND c.date = :day ORDER BY c.pct, s.name, c.pollutant"
            ),
            {"d": district.id, "day": day},
        )
        .mappings()
        .all()
    )
    excluded = excluded_readings(readings) if not readings.empty else None
    summary = latest_summary(session, district.id, day)
    return {
        "date": day,
        "completeness_pct": summary.completeness_pct if summary else None,
        "computed_at": summary.computed_at if summary else None,
        "gap_bias": None
        if summary is None or summary.gap_bias_flag is None
        else {
            "flagged": summary.gap_bias_flag,
            "polluted_hours_missing_pct": summary.polluted_missing_pct,
            "clean_hours_missing_pct": summary.clean_missing_pct,
            "difference_pp": summary.gap_bias_diff_pp,
        },
        "silent_stations": [
            {"station_id": sid, "name": names.get(sid), "from": a, "to": b}
            for sid, runs in (silence.silent_stations.items() if silence else [])
            for a, b in runs
        ],
        "city_silent_hours": silence.city_silent_hours if silence else [],
        "readings_near_limit": []
        if excluded is None
        else [
            {
                "station_id": int(r.station_id),
                "name": names.get(int(r.station_id)),
                "hour": r.hour.to_pydatetime(),
                "pollutant": r.pollutant,
                "value": r.value,
                "at_or_over_999": bool(r.at_or_over_limit),
            }  # fmt: skip
            for r in excluded.itertuples()
        ],
        "stations": [dict(r) for r in per_station],
    }


def gap_csv(report: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["station_id", "station", "pollutant", "expected_hours", "received_hours",
                "excluded_hours", "completeness_pct", "longest_gap_hours"])  # fmt: skip
    for r in report["stations"]:
        w.writerow([r["station_id"], r["name"], r["pollutant"], r["expected"], r["received"],
                    r["excluded"], r["pct"], r["longest_gap_hours"]])  # fmt: skip
    return buf.getvalue()
