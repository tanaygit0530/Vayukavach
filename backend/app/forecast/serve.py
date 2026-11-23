"""Nightly forecast job: gate on the backtest, retrain, write the 10-day forecast.

Fallbacks (spec): if the bias model does not beat its baselines, days 1-5 use raw CAMS;
if the outlook does not, days 6-10 are not served.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.analysis.hourly import running_city_aqi
from app.analysis.time import day_bounds
from app.forecast.model import (
    POLLUTANTS,
    Backtest,
    BiasModel,
    OutlookModel,
    backtest,
    build_frame,
    outlook_rows,
    summary,
)
from app.models import (
    AqiForecastDaily,
    CityDailyAqi,
    District,
    DistrictDailyFeatures,
    ForecastModel,
)

IST = timedelta(hours=5, minutes=30)


def today_ist(now: datetime) -> date:
    return (now + IST).date()


def load_frame(session: Session) -> pd.DataFrame:
    target = pd.read_sql(
        select(
            CityDailyAqi.district_id,
            CityDailyAqi.date,
            CityDailyAqi.aqi,
            *[getattr(CityDailyAqi, p) for p in POLLUTANTS],
        ),
        session.connection(),
    )
    feats = pd.read_sql(select(DistrictDailyFeatures), session.connection())
    feats = feats.drop(columns=["id", "is_forecast", "fetched_at"])
    if feats.empty:
        return feats
    return build_frame(target, feats)


@dataclass
class NightlyResult:
    version: str
    summary: dict
    rows_written: int
    backtest: Backtest


def _hourly_low_high(
    session: Session,
    district_id: int,
    factors: dict[date, dict[str, float]],
    start: datetime,
    end: datetime,
) -> dict[date, tuple[float, float, float]]:
    """Daily (min, max, mean) of the running AQI from hourly CAMS scaled by each day's
    correction factors: the shape of the day, used to spread the range around the model."""
    rows = session.execute(
        text(
            "SELECT hour, pollutant, value FROM model_air WHERE district_id = :d AND hour >= :s"
            " AND hour < :e AND pollutant = ANY(:p) AND value IS NOT NULL"
        ),
        {"d": district_id, "s": start, "e": end, "p": list(POLLUTANTS)},
    ).all()
    if not rows:
        return {}
    df = pd.DataFrame(rows, columns=["hour", "pollutant", "value"])
    df["hour"] = pd.to_datetime(df["hour"], utc=True)
    df["day"] = (df["hour"] + IST).dt.date
    df["value"] = [
        v * factors.get(d, {}).get(p, 1.0)
        for v, d, p in zip(df["value"], df["day"], df["pollutant"], strict=True)
    ]
    frames = {
        p: g.groupby("hour")["value"].mean().to_frame(name=0) for p, g in df.groupby("pollutant")
    }
    series = running_city_aqi(frames)
    series = series[series["aqi"].notna()]
    out = {}
    for day, g in series.groupby((series.index + IST).date):
        out[day] = (float(g["aqi"].min()), float(g["aqi"].max()), float(g["aqi"].mean()))
    return out


def run_nightly(session: Session, now: datetime | None = None, weeks: int = 52) -> NightlyResult:
    now = now or datetime.now(UTC)
    today = today_ist(now)
    df = load_frame(session)
    past = df[df["date"] < today]

    bt = backtest(past, end=today - timedelta(days=1), weeks=weeks)
    s = summary(bt)
    version = f"{today.isoformat()}T{now:%H%M}"
    train = past[past["aqi"].notna()]
    rows_out = outlook_rows(past)
    for kind, beats, n in (
        ("bias", s["bias_beats_baseline"], len(train)),
        ("outlook", s["outlook_beats_baseline"], len(rows_out)),
    ):
        stmt = insert(ForecastModel).values(
            kind=kind,
            version=f"{kind}-{version}",
            trained_at=now,
            train_rows=n,
            metrics={**s, "table": bt.table.round(3).to_dict("records")},
            beats_baseline=beats,
            notes=f"{weeks}-week rolling weekly backtest",
        )
        session.execute(stmt.on_conflict_do_nothing(index_elements=["version"]))

    bias = BiasModel().fit(train)
    outlook = OutlookModel().fit(rows_out) if s["outlook_beats_baseline"] else None
    created = datetime.now(UTC)
    written = 0
    for district in session.execute(select(District)).scalars():
        g = df[df["district_id"] == district.id].set_index("date")
        rows = []
        # ---- days 1-5
        targets = [today + timedelta(days=i) for i in range(5)]
        # A district without station history (e.g. Shimla) has nothing to correct against and
        # no backtest: it stays on raw CAMS.
        use_bias = s["bias_beats_baseline"] and bool(bias.models) and district.id in bias.districts
        corr = (
            bias.corrected_values(df[df["district_id"] == district.id], today)
            if use_bias
            else pd.DataFrame()
        )
        corr = corr.set_index("target_date") if not corr.empty else corr
        factors: dict[date, dict[str, float]] = {}
        medians: dict[date, int | None] = {}
        for t in targets:
            if t not in g.index:
                continue
            r = g.loc[t]
            if use_bias and t in corr.index:
                c = corr.loc[t]
                factors[t] = {
                    p: float(c[f"corr_{p}"] / r[f"cams_{p}"])
                    for p in POLLUTANTS
                    if pd.notna(r[f"cams_{p}"]) and r[f"cams_{p}"] > 0 and pd.notna(c[f"corr_{p}"])
                }
                medians[t] = None if c["corrected_aqi"] is None else int(c["corrected_aqi"])
            else:
                medians[t] = None if pd.isna(r["cams_aqi"]) else int(r["cams_aqi"])
        if medians:
            start = day_bounds(today)[0] - timedelta(hours=24)
            ranges = _hourly_low_high(
                session, district.id, factors, start, day_bounds(targets[-1])[1]
            )
            for t in targets:
                if t in medians:
                    rows.append(
                        _row(
                            district.id,
                            today,
                            t,
                            centred_range(ranges.get(t), medians[t]),
                            medians[t],
                            "cams_corrected" if use_bias else "cams_raw",
                            version,
                            created,
                        )
                    )
        # ---- days 6-10
        if outlook is not None:
            orows = outlook_rows(df[(df["district_id"] == district.id)], issue_dates=[today])
            if not orows.empty:
                q = outlook.predict(orows)
                for (_, r), (_, qq) in zip(orows.iterrows(), q.iterrows(), strict=True):
                    rows.append(
                        _row(
                            district.id,
                            today,
                            r["target_date"],
                            (int(round(qq["low"])), int(round(qq["high"]))),
                            int(round(qq["mid"])),
                            "outlook",
                            version,
                            created,
                        )
                    )
        if rows:
            stmt = insert(AqiForecastDaily).values(rows)
            session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["district_id", "issue_date", "target_date"],
                    set_={
                        k: stmt.excluded[k]
                        for k in rows[0]
                        if k not in ("district_id", "issue_date", "target_date")
                    },
                )
            )
            written += len(rows)
    session.commit()
    return NightlyResult(version, s, written, bt)


def centred_range(spread: tuple[float, float, float] | None, median: int | None):
    """Daily low/high: the hourly spread (min/max around the hourly mean), shifted so that it is
    centred on the model's daily value. Without hourly data there is no range."""
    if spread is None or median is None:
        return None
    lo, hi, mean = spread
    shift = median - mean
    return (max(0, int(round(lo + shift))), min(500, int(round(hi + shift))))


def _row(district_id, issue, target, lo_hi, median, method, version, created) -> dict:
    lo, hi = lo_hi if lo_hi else (None, None)
    if median is not None and lo is not None:
        lo, hi = min(lo, median), max(hi, median)
    return {
        "district_id": district_id,
        "issue_date": issue,
        "target_date": target,
        "lead_days": (target - issue).days + 1,
        "low": lo,
        "median": median,
        "high": hi,
        "method": method,
        "model_version": version,
        "created_at": created,
    }
