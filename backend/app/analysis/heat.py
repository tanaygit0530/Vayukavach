"""Humid-heat risk: heat index, wet-bulb temperature, level, safe work hours, tips.

Heat index: US National Weather Service regression (Rothfusz, NWS SR 90-23) with its
published low/high humidity adjustments; below 80 degF the NWS simple formula is used.
Wet-bulb: Stull (2011), "Wet-Bulb Temperature from Relative Humidity and Air Temperature",
J. Appl. Meteor. Climatol. 50, 2267-2269 (valid for RH 5-99 %, -20 to 50 degC; error < 1 degC).

LEVEL THRESHOLDS ARE A DRAFT, to be aligned with the district heat action plan.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

# ---------------------------------------------------------------- formulas


def heat_index_c(temp_c: float, rh: float) -> float:
    """NWS heat index in degC from air temperature (degC) and relative humidity (%)."""
    t = temp_c * 9 / 5 + 32
    simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
    if (simple + t) / 2 < 80:
        hi = simple
    else:
        hi = (
            -42.379 + 2.04901523 * t + 10.14333127 * rh - 0.22475541 * t * rh
            - 0.00683783 * t * t - 0.05481717 * rh * rh + 0.00122874 * t * t * rh
            + 0.00085282 * t * rh * rh - 0.00000199 * t * t * rh * rh
        )  # fmt: skip
        if rh < 13 and 80 <= t <= 112:
            hi -= ((13 - rh) / 4) * math.sqrt((17 - abs(t - 95)) / 17)
        elif rh > 85 and 80 <= t <= 87:
            hi += ((rh - 85) / 10) * ((87 - t) / 5)
    return (hi - 32) * 5 / 9


def wet_bulb_c(temp_c: float, rh: float) -> float:
    """Stull (2011) wet-bulb temperature in degC."""
    t, r = temp_c, rh
    return (
        t * math.atan(0.151977 * math.sqrt(r + 8.313659))
        + math.atan(t + r)
        - math.atan(r - 1.676331)
        + 0.00391838 * r**1.5 * math.atan(0.023101 * r)
        - 4.686035
    )


# ---------------------------------------------------------------- levels (DRAFT)

LEVELS = ("normal", "caution", "danger", "extreme")
LEVEL_NAMES = {"normal": "Normal", "caution": "Caution", "danger": "Danger", "extreme": "Extreme"}
# (level, heat index degC at or above, wet-bulb degC at or above). Heat-index bands follow the
# NWS categories (Extreme caution 32, Danger 41, Extreme danger 54); wet-bulb bands follow
# occupational guidance that sustained work becomes unsafe from about 28-31 degC wet-bulb.
THRESHOLDS = (("extreme", 54.0, 31.0), ("danger", 41.0, 28.0), ("caution", 32.0, 26.0))
THRESHOLDS_STATUS = "draft, to be aligned with the district heat action plan"

WORK_REST = {
    "normal": "Normal work. Drink water regularly.",
    "caution": "Shaded break every hour. Drink a cup of water every 20 minutes.",
    "danger": "Heavy work only before 11 AM and after 4 PM. 30-minute shaded break each hour.",
    "extreme": "Stop heavy outdoor work. Rest in shade, drink water often, watch each other.",
}


def level_for(heat_index: float | None, wet_bulb: float | None) -> str | None:
    if heat_index is None and wet_bulb is None:
        return None
    for level, hi_min, wb_min in THRESHOLDS:
        if (heat_index is not None and heat_index >= hi_min) or (
            wet_bulb is not None and wet_bulb >= wb_min
        ):
            return level
    return "normal"


# ---------------------------------------------------------------- tips (NDMA)

TIPS_SOURCE = "NDMA, Heat Wave: Do's and Don'ts (ndma.gov.in)"
TIPS = {
    "normal": [
        "Drink enough water through the day, even if you are not thirsty.",
    ],
    "caution": [
        "Drink water often; carry water when you travel.",
        "Wear light, loose, light-coloured cotton clothes and cover your head.",
        "Use ORS or home drinks such as lassi, lemon water or buttermilk.",
    ],
    "danger": [
        "Avoid going out in the sun, especially between 12 noon and 3 PM.",
        "Avoid strenuous work outdoors in the hottest hours; take frequent breaks.",
        "Employers: give cool drinking water and shade, and move heavy jobs to cooler hours.",
    ],
    "extreme": [
        "Stay indoors or in shade during the day if you can.",
        "Heatstroke signs (confusion, hot dry skin, fainting): call 108 and cool the person.",
    ],
}


def tips_for(level: str) -> list[str]:
    """Tips for a level include the tips of all milder levels."""
    out: list[str] = []
    for name in LEVELS[: LEVELS.index(level) + 1]:
        out.extend(TIPS[name])
    return out


# ---------------------------------------------------------------- hours


@dataclass(frozen=True)
class HeatHour:
    hour: datetime  # hour start (UTC)
    local_hour: int  # IST clock hour 0-23
    temperature: float | None
    humidity: float | None
    apparent_temperature: float | None
    heat_index: float | None
    wet_bulb: float | None
    level: str | None


def assess_hour(hour, local_hour, temperature, humidity, apparent=None) -> HeatHour:
    if temperature is None or humidity is None:
        return HeatHour(hour, local_hour, temperature, humidity, apparent, None, None, None)
    hi = heat_index_c(temperature, humidity)
    wb = wet_bulb_c(temperature, min(max(humidity, 5.0), 99.0))
    return HeatHour(
        hour, local_hour, temperature, humidity, apparent, round(hi, 1), round(wb, 1),
        level_for(hi, wb),
    )  # fmt: skip


WORK_DAY = (6, 19)  # 6 AM to 7 PM IST


def safe_windows(hours: Sequence[HeatHour], work_day=WORK_DAY) -> list[tuple[int, int]]:
    """Continuous IST hour ranges [start, end) within the work day where the level is
    Normal (below Caution). Hours without data are not counted as safe."""
    start, end = work_day
    by_hour = {h.local_hour: h for h in hours}
    windows: list[tuple[int, int]] = []
    run_start = None
    for clock in range(start, end):
        h = by_hour.get(clock)
        safe = h is not None and h.level == "normal"
        if safe and run_start is None:
            run_start = clock
        if not safe and run_start is not None:
            windows.append((run_start, clock))
            run_start = None
    if run_start is not None:
        windows.append((run_start, end))
    return windows


def worst_level(hours: Sequence[HeatHour]) -> str | None:
    levels = [h.level for h in hours if h.level]
    return max(levels, key=LEVELS.index) if levels else None
