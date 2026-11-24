"""Hold-out test of the shadow estimates on stored station history (read-only).

For every covered city and IST day: hide 10% of the real hourly readings, estimate them the
way the shadow AQI does (inverse-distance weighting of stations within 15 km, same hour),
and compare with the truth. Baseline on the same hidden cells: the mean of all other
stations in the city that hour. Writes docs/validation/shadow_holdout.md.

    DATABASE_URL=<read access> uv run python scripts/validate_shadow.py [days]
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analysis.aqi import sub_index  # noqa: E402
from app.analysis.shadow import HOLDOUT_FRACTION, RADIUS_KM, fill_missing  # noqa: E402
from app.analysis.summary import (  # noqa: E402
    RECEIVED,
    _frames,
    load_readings,
    load_reference_stations,
)
from app.analysis.time import day_bounds, day_hours, ist_date  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.models import District  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "validation" / "shadow_holdout.md"
POLLUTANTS = ("pm25", "pm10")


def holdout(frame: pd.DataFrame, coords, rng) -> list[tuple[float, float, float]]:
    """(truth, ours, baseline) for each hidden cell that both methods could estimate."""
    real = frame.stack().dropna()
    if len(real) < 20:
        return []
    k = max(1, int(round(len(real) * HOLDOUT_FRACTION)))
    picked = real.index[rng.choice(len(real), size=k, replace=False)]
    hidden = frame.copy()
    for hour, station in picked:
        hidden.at[hour, station] = np.nan
    ours, mask = fill_missing(hidden, coords)
    baseline = hidden.mean(axis=1)  # other stations, same hour
    out = []
    for hour, station in picked:
        if mask.at[hour, station] and pd.notna(baseline.at[hour]):
            out.append((real.loc[(hour, station)], ours.at[hour, station], baseline.at[hour]))
    return out


def city_pm25_index(frame: pd.DataFrame) -> float | None:
    """City PM2.5 sub-index for the day: mean over stations of each station's daily-mean
    sub-index (stations with no value that day are left out, as in the official city AQI)."""
    means = frame.mean(axis=0).dropna()
    subs = [sub_index("pm25", v) for v in means]
    subs = [x for x in subs if x is not None]
    return float(np.mean(subs)) if subs else None


def peak_gaps(frame: pd.DataFrame) -> pd.DataFrame:
    """Diwali-style gaps: in the day's 6 most polluted hours, the most polluted third of the
    stations go silent."""
    hidden = frame.copy()
    worst_hours = frame.mean(axis=1).nlargest(6).index
    for hour in worst_hours:
        row = frame.loc[hour].dropna()
        k = max(1, len(row) // 3)
        hidden.loc[hour, row.nlargest(k).index] = np.nan
    return hidden


def ratio_fill(hidden: pd.DataFrame) -> pd.DataFrame:
    """Prototype: each station's usual ratio to the mean of the other stations (median over the
    hours both reported that day) times the other stations' mean in the missing hour."""
    filled = hidden.copy()
    for s in hidden.columns:
        others = hidden.drop(columns=s).mean(axis=1)
        both = hidden[s].notna() & others.notna() & (others > 0)
        if both.sum() < 4:
            continue
        ratio = float((hidden.loc[both, s] / others[both]).median())
        gap = hidden[s].isna() & others.notna()
        filled.loc[gap, s] = ratio * others[gap]
    return filled


def city_test(frame: pd.DataFrame, coords, rng) -> list[tuple[str, float, float, float]]:
    """(scheme, truth, official-style without the hidden hours, shadow) city PM2.5 index."""
    truth = city_pm25_index(frame)
    real = frame.stack().dropna()
    if truth is None or len(real) < 40 or frame.shape[1] < 3:
        return []
    random_hidden = frame.copy()
    k = max(1, int(round(len(real) * HOLDOUT_FRACTION)))
    for hour, station in real.index[rng.choice(len(real), size=k, replace=False)]:
        random_hidden.at[hour, station] = np.nan
    out = []
    for scheme, hidden in (("random", random_hidden), ("peak", peak_gaps(frame))):
        filled, _ = fill_missing(hidden, coords)
        dropped, shadow = city_pm25_index(hidden), city_pm25_index(filled)
        ratio = city_pm25_index(ratio_fill(hidden))
        if dropped is not None and shadow is not None and ratio is not None:
            out.append((scheme, truth, dropped, shadow, ratio))
    return out


def main(days: int) -> None:
    engine = create_engine(get_settings().database_url)
    end_day = ist_date(datetime.now(UTC)) - timedelta(days=1)
    first_day = end_day - timedelta(days=days - 1)
    rng = np.random.default_rng(42)
    rows = []
    city_rows = []
    with Session(engine) as s:
        for d in s.execute(select(District).order_by(District.name)).scalars():
            coords = load_reference_stations(s, d.id)
            if len(coords) < 2:
                continue
            start, _ = day_bounds(first_day)
            _, stop = day_bounds(end_day)
            readings = load_readings(s, list(coords), start, stop)
            if readings.empty:
                continue
            day = first_day
            while day <= end_day:
                a, b = day_bounds(day)
                part = readings[(readings["hour"] >= a) & (readings["hour"] < b)]
                frames = _frames(part, RECEIVED, day_hours(day)) if not part.empty else {}
                for p in POLLUTANTS:
                    if p in frames:
                        for truth, ours, base in holdout(frames[p], coords, rng):
                            rows.append((d.name, p, day, truth, ours, base))
                if "pm25" in frames:
                    for scheme, truth, dropped, shadow, ratio in city_test(
                        frames["pm25"], coords, rng
                    ):
                        city_rows.append((d.name, day, scheme, truth, dropped, shadow, ratio))
                day += timedelta(days=1)
            print(f"{d.name}: {sum(1 for r in rows if r[0] == d.name)} hidden readings", flush=True)
    df = pd.DataFrame(rows, columns=["city", "pollutant", "day", "truth", "ours", "base"])
    df["err"] = (df["ours"] - df["truth"]).abs()
    df["base_err"] = (df["base"] - df["truth"]).abs()

    def table(g: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "n": g.groupby(level=0)["err"].size(),
                "mean": g.groupby(level=0)["truth"].mean(),
                "mae": g.groupby(level=0)["err"].mean(),
                "base_mae": g.groupby(level=0)["base_err"].mean(),
            }
        )

    lines = [
        "# Shadow AQI estimates: hold-out test",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by"
        " `backend/scripts/validate_shadow.py` on stored CPCB/SPCB station data (OpenAQ),"
        f" {first_day} to {end_day} ({days} days).",
        "",
        f"Each day, {HOLDOUT_FRACTION:.0%} of the real hourly readings per city and pollutant were"
        f" hidden and estimated from stations within {RADIUS_KM:.0f} km in the same hour"
        " (the shadow AQI method). Baseline: the mean of all other stations in the city that"
        " hour. Only cells both methods could estimate are scored. Errors are in µg/m³.",
        "",
    ]
    for p in POLLUTANTS:
        sub = df[df["pollutant"] == p].set_index("city")
        if sub.empty:
            continue
        t = table(sub)
        allrow = (len(sub), sub["truth"].mean(), sub["err"].mean(), sub["base_err"].mean())
        name = {"pm25": "PM2.5", "pm10": "PM10"}[p]
        lines += [
            f"## {name}",
            "",
            "| City | Hidden readings | Mean level | Shadow error (MAE) | Relative"
            " | Baseline MAE |",
            "|---|--:|--:|--:|--:|--:|",
        ]
        for city, r in t.sort_values("n", ascending=False).iterrows():
            lines.append(
                f"| {city} | {int(r.n):,} | {r['mean']:.0f} | **{r.mae:.1f}** |"
                f" {100 * r.mae / r['mean']:.0f}% | {r.base_mae:.1f} |"
            )
        n, mean, mae, base = allrow
        gain = 100 * (1 - mae / base)
        verdict = (
            f"{gain:.0f}% closer to the truth than the city-mean baseline"
            if gain >= 3
            else f"about as accurate as the city-mean baseline ({gain:+.0f}%)"
        )
        lines += [
            f"| **All cities** | **{n:,}** | {mean:.0f} | **{mae:.1f}** | {100 * mae / mean:.0f}% |"
            f" {base:.1f} |",
            "",
            f"Single hidden readings: shadow estimates are {verdict}.",
            "",
        ]
    c = pd.DataFrame(
        city_rows, columns=["city", "day", "scheme", "truth", "dropped", "shadow", "ratio"]
    )
    c["ratio_err"] = (c["ratio"] - c["truth"]).abs()
    c["ratio_bias"] = c["ratio"] - c["truth"]
    c["drop_err"] = (c["dropped"] - c["truth"]).abs()
    c["shadow_err"] = (c["shadow"] - c["truth"]).abs()
    c["drop_bias"] = c["dropped"] - c["truth"]
    c["shadow_bias"] = c["shadow"] - c["truth"]
    lines += [
        "## City PM2.5 index for the day (what the app shows)",
        "",
        "City PM2.5 sub-index (India AQI scale) from all real readings = truth. Then readings are"
        " hidden and the index is recomputed two ways: **without** the hidden hours (what an"
        " official average does) and with them **filled by the shadow method**.",
        "",
        "- *Random gaps*: 10% of readings hidden at random.",
        "- *Peak gaps* (Diwali-style): in the 6 most polluted hours, the most polluted third of"
        " the stations go silent.",
        "",
        "| Gaps | City-days | Error without the gaps (AQI points) | Bias | Shadow error | Bias"
        " | Ratio-scaled prototype | Bias |",
        "|---|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for scheme, label in (("random", "Random"), ("peak", "Peak (Diwali-style)")):
        g = c[c["scheme"] == scheme]
        if g.empty:
            continue
        lines.append(
            f"| {label} | {len(g):,} | {g.drop_err.mean():.1f} | {g.drop_bias.mean():+.1f} |"
            f" **{g.shadow_err.mean():.1f}** | {g.shadow_bias.mean():+.1f} |"
            f" {g.ratio_err.mean():.1f} | {g.ratio_bias.mean():+.1f} |"
        )
    peak = c[c["scheme"] == "peak"]
    if not peak.empty:
        lines += [
            "",
            f"With Diwali-style gaps, leaving the gaps out reads **{-peak.drop_bias.mean():.1f}"
            f" points too clean** on average; the shadow index cuts that error by"
            f" {100 * (1 - peak.shadow_err.mean() / peak.drop_err.mean()):.0f}%. The ratio-scaled"
            " prototype (each station's usual ratio to the rest of the city that day, times the"
            " city in the missing hour) cuts it by"
            f" {100 * (1 - peak.ratio_err.mean() / peak.drop_err.mean()):.0f}%; it is not in the"
            " app yet.",
            "",
            "With random gaps, leaving them out is already accurate (daily means barely move), and"
            " filling adds estimation noise. The shadow index is useful when gaps cluster in"
            " polluted hours, which the app flags as *missing when it mattered*.",
            "",
            "| City | City-days | Without the gaps | Shadow |",
            "|---|--:|--:|--:|",
        ]
        for city, g in peak.groupby("city"):
            lines.append(
                f"| {city} | {len(g)} | {g.drop_err.mean():.1f} | **{g.shadow_err.mean():.1f}** |"
            )
        lines.append("")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
