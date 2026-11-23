from datetime import date

import pandas as pd

from app.analysis.time import day_hours

DAY = date(2026, 11, 8)  # Diwali
HOURS = day_hours(DAY)


def readings(spec: dict[tuple[int, str], list[float | None | str]]) -> pd.DataFrame:
    """Build a readings frame. Each list has 24 entries: a number (ok), None (missing row),
    'x' (excluded value 1200) or '-' (no row at all)."""
    rows = []
    for (station, pollutant), values in spec.items():
        assert len(values) == 24
        for hour, v in zip(HOURS, values, strict=True):
            if v == "-":
                continue
            if v == "x":
                rows.append((station, hour, pollutant, "excluded_over_999", 1200.0))
            elif v is None:
                rows.append((station, hour, pollutant, "missing", None))
            else:
                rows.append((station, hour, pollutant, "ok", float(v)))
    return pd.DataFrame(rows, columns=["station_id", "hour", "pollutant", "status", "value"])
