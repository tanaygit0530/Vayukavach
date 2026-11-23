"""AQI forecasting: CAMS bias correction (days 1-5) and a quantile outlook (days 6-10).

Day numbering: on issue date t, "day 1" is t itself (today), day L targets t + (L - 1).
The latest AQI known at issue time is t - 1 (today's daily value is incomplete).

Honest limits (also printed in the backtest report):
- The CAMS archive holds analyses, not the forecasts issued in the past, so the days 1-5
  backtest uses CAMS at lead 0 for every day: an upper bound on real skill.
- The outlook backtest uses observed (reanalysis) weather for target days, where live serving
  uses the weather forecast: also an upper bound.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

import lightgbm as lgb
import numpy as np
import pandas as pd

from app.analysis.aqi import aqi_from_concentrations, category

POLLUTANTS = ("pm25", "pm10", "no2", "so2", "co", "o3")
# All six: CAMS ozone runs high in India and, left raw, set the "corrected" AQI in 35 of 45
# test cases (backtest diagnosis, 2026-11-23).
CORRECTED = POLLUTANTS
WEATHER = ("temperature_mean", "humidity_mean", "wind_mean", "precipitation_sum", "blh_mean")
OUTLOOK_DAYS = (6, 7, 8, 9, 10)
QUANTILES = (0.05, 0.5, 0.95)  # nominal 90% band; backtest reports the real coverage
LGB_PARAMS = dict(
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=15,
    min_child_samples=20,
    subsample=0.9,
    subsample_freq=1,
    colsample_bytree=0.9,
    verbose=-1,
)

# Diwali (Lakshmi Puja) dates; the window is the 2 days before to 3 days after.
DIWALI = (date(2024, 11, 1), date(2025, 10, 20), date(2026, 11, 8), date(2027, 10, 29))


def festival_flag(d: date) -> int:
    return int(any(-2 <= (d - f).days <= 3 for f in DIWALI))


def stubble_flag(d: date) -> int:
    """Stubble-burning season in Punjab/Haryana: 15 Sep - 30 Nov."""
    return int((d.month == 9 and d.day >= 15) or d.month in (10, 11))


def calendar(d: date) -> dict:
    m = 2 * math.pi * (d.month - 1) / 12
    return {
        "month_sin": math.sin(m),
        "month_cos": math.cos(m),
        "dow": d.weekday(),
        "festival": festival_flag(d),
        "stubble": stubble_flag(d),
    }


def aqi_of(row: dict, prefix: str = "") -> int | None:
    res = aqi_from_concentrations({p: row.get(f"{prefix}{p}") for p in POLLUTANTS})
    return res.aqi if res.valid else None


def cat_key(aqi: float | None) -> str | None:
    c = category(aqi) if aqi is not None and not np.isnan(aqi) else None
    return c[1] if c else None


# ---------------------------------------------------------------- data frame


def build_frame(target: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    """One row per (district, date): target AQI/pollutants + CAMS + weather + calendar."""
    df = features.merge(target, on=["district_id", "date"], how="left")
    df = df.sort_values(["district_id", "date"]).reset_index(drop=True)
    cams = [aqi_of(r, "cams_") for r in df.to_dict("records")]
    df["cams_aqi"] = pd.array(cams, dtype="Int64").astype("float")
    cal = pd.DataFrame([calendar(d) for d in df["date"]])
    return pd.concat([df, cal], axis=1)


# ---------------------------------------------------------------- days 1-5: bias correction

EARLY_DAYS = (1, 2, 3, 4, 5)


def _daily_index(g: pd.DataFrame) -> pd.DataFrame:
    """Reindex one district to every calendar day, so shift(n) means n days."""
    g = g.set_index("date").sort_index()
    full = pd.date_range(min(g.index), max(g.index), freq="D").date
    return g.reindex(full)


def bias_rows(df: pd.DataFrame, pollutant: str, leads=EARLY_DAYS) -> pd.DataFrame:
    """Rows (district, issue t, day L, target = t + L - 1): CAMS and weather for the target
    day, the station value observed on t - 1 (lag1) and the mean of t-1..t-3 (mean3)."""
    out = []
    for district, g in df.groupby("district_id"):
        g = _daily_index(g)
        obs = g[pollutant]
        mean3 = obs.rolling(3, min_periods=1).mean()
        for lead in leads:
            f = pd.DataFrame(
                {
                    "district_id": district,
                    "target_date": g.index,
                    "lead": lead,
                    "issue": [d - timedelta(days=lead - 1) for d in g.index],
                    "cams": g[f"cams_{pollutant}"],
                    "y": obs,
                    "lag1": obs.shift(lead),
                    "mean3": mean3.shift(lead),
                    **{
                        c: g[c] for c in ("month_sin", "month_cos", "festival", "stubble", *WEATHER)
                    },
                }
            )
            out.append(f)
    rows = pd.concat(out, ignore_index=True)
    return rows[rows["cams"].notna()]


def _bias_x(rows: pd.DataFrame, districts: list[int]) -> pd.DataFrame:
    x = pd.DataFrame(
        {
            "cams": np.log1p(rows["cams"].clip(lower=0)),
            "lag1": np.log1p(rows["lag1"].clip(lower=0)),
            "mean3": np.log1p(rows["mean3"].clip(lower=0)),
            "lead": rows["lead"],
            **{c: rows[c] for c in ("month_sin", "month_cos", "festival", "stubble", *WEATHER)},
            "district": pd.Categorical(rows["district_id"], categories=districts),
        }
    )
    x["blh_mean"] = np.log1p(x["blh_mean"].clip(lower=0))
    return x


@dataclass
class BiasModel:
    """Model-output statistics: corrects CAMS PM2.5/PM10 using the station values observed up
    to the day before the issue date (as forecasters do), per day ahead 1-5."""

    models: dict[str, lgb.LGBMRegressor] = field(default_factory=dict)
    districts: list[int] = field(default_factory=list)

    def fit(self, df: pd.DataFrame) -> BiasModel:
        self.districts = sorted(df["district_id"].unique())
        for p in CORRECTED:
            rows = bias_rows(df, p)
            rows = rows[rows["y"].notna()]
            if len(rows) < 60:
                continue
            self.models[p] = lgb.LGBMRegressor(**LGB_PARAMS).fit(
                _bias_x(rows, self.districts), np.log1p(rows["y"].clip(lower=0))
            )
        return self

    def corrected_values(self, df: pd.DataFrame, issue: date) -> pd.DataFrame:
        """For issue date `issue`: per (district, target) corrected PM and CAMS others."""
        frames = []
        for p in CORRECTED:
            rows = bias_rows(df, p)
            rows = rows[rows["issue"] == issue]
            if p in self.models and not rows.empty:
                rows = rows.assign(
                    **{f"corr_{p}": np.expm1(self.models[p].predict(_bias_x(rows, self.districts)))}
                )
            elif not rows.empty:
                rows = rows.assign(**{f"corr_{p}": rows["cams"]})
            frames.append(rows[["district_id", "target_date", "lead", f"corr_{p}"]])
        if not frames:
            return pd.DataFrame()
        out = frames[0]
        for f in frames[1:]:
            out = out.merge(f, on=["district_id", "target_date", "lead"], how="outer")
        base = df.set_index(["district_id", "date"])
        keys = list(zip(out["district_id"], out["target_date"], strict=True))
        cams = base.reindex(keys)
        for p in POLLUTANTS:
            if p not in CORRECTED:
                out[f"corr_{p}"] = cams[f"cams_{p}"].to_numpy()
            out[f"cams_{p}"] = cams[f"cams_{p}"].to_numpy()
        out["corrected_aqi"] = [aqi_of(r, "corr_") for r in out.to_dict("records")]
        return out


# ---------------------------------------------------------------- days 6-10: outlook


def outlook_rows(
    df: pd.DataFrame, issue_dates: list[date] | None = None, leads=OUTLOOK_DAYS
) -> pd.DataFrame:
    """Rows (district, issue date t, day L) with lags ending at t-1 and target-day features."""
    rows = []
    for district, g in df.groupby("district_id"):
        g = g.set_index("date").sort_index()
        aqi = g["aqi"]
        dates = issue_dates or list(g.index)
        for t in dates:
            lags = [aqi.get(t - timedelta(days=k)) for k in range(1, 8)]
            if lags[0] is None or pd.isna(lags[0]):
                continue
            lagvals = [np.nan if v is None or pd.isna(v) else float(v) for v in lags]
            for lead in leads:
                target = t + timedelta(days=lead - 1)
                if target not in g.index:
                    continue
                f = g.loc[target]
                rows.append(
                    {
                        "district_id": district,
                        "issue": t,
                        "target_date": target,
                        "lead": lead,
                        "y": f["aqi"],
                        **{f"lag{k}": lagvals[k - 1] for k in range(1, 8)},
                        "mean7": np.nanmean(lagvals),
                        "max7": np.nanmax(lagvals),
                        **{
                            c: f[c]
                            for c in ("month_sin", "month_cos", "dow", "festival", "stubble")
                        },
                        **{w: f[w] for w in WEATHER},
                    }
                )
    return pd.DataFrame(rows)


OUTLOOK_X = (
    ["lead", "mean7", "max7"]
    + [f"lag{k}" for k in range(1, 8)]
    + ["month_sin", "month_cos", "dow", "festival", "stubble", *WEATHER, "district"]
)


@dataclass
class OutlookModel:
    models: dict[float, lgb.LGBMRegressor] = field(default_factory=dict)
    districts: list[int] = field(default_factory=list)

    def _x(self, rows: pd.DataFrame) -> pd.DataFrame:
        x = rows.assign(district=pd.Categorical(rows["district_id"], categories=self.districts))
        return x[OUTLOOK_X]

    def fit(self, rows: pd.DataFrame) -> OutlookModel:
        rows = rows[rows["y"].notna()]
        self.districts = sorted(rows["district_id"].unique())
        for q in QUANTILES:
            self.models[q] = lgb.LGBMRegressor(objective="quantile", alpha=q, **LGB_PARAMS).fit(
                self._x(rows), rows["y"].astype(float)
            )
        return self

    def predict(self, rows: pd.DataFrame) -> pd.DataFrame:
        x = self._x(rows)
        names = dict(zip(QUANTILES, ("low", "mid", "high"), strict=True))
        out = pd.DataFrame(
            {names[q]: self.models[q].predict(x) for q in QUANTILES}, index=rows.index
        )
        # quantile models are fit separately: sort so low <= median <= high
        out[:] = np.sort(out.to_numpy(), axis=1)
        return out.clip(lower=0, upper=500)


# ---------------------------------------------------------------- backtest


@dataclass
class Backtest:
    table: pd.DataFrame  # per (day, method): n, mae, hit_rate
    coverage_80: float | None  # share of truths inside the outlook's 10-90% band
    issues: int
    start: date
    end: date


def _score(pred: pd.Series, truth: pd.Series) -> tuple[int, float, float]:
    ok = pred.notna() & truth.notna()
    if not ok.any():
        return 0, float("nan"), float("nan")
    p, y = pred[ok].astype(float), truth[ok].astype(float)
    hits = np.mean([cat_key(a) == cat_key(b) for a, b in zip(p, y, strict=True)])
    return int(ok.sum()), float(np.abs(p - y).mean()), float(hits)


def backtest(df: pd.DataFrame, end: date, weeks: int = 52, min_train_days: int = 120) -> Backtest:
    """Rolling weekly issues over `weeks` before `end`; models retrained on data before t."""
    issues = [end - timedelta(days=7 * k + 10) for k in range(weeks)][::-1]
    preds = []
    for t in issues:
        past = df[df["date"] < t]
        if past["aqi"].notna().sum() < min_train_days:
            continue
        bias = BiasModel().fit(past[past["aqi"].notna()])
        orow = outlook_rows(past)
        outlook = OutlookModel().fit(orow) if len(orow) > 200 else None
        clim = past.groupby(["district_id", past["date"].map(lambda d: d.month)])["aqi"].mean()
        rows = outlook_rows(df, issue_dates=[t], leads=range(1, 11))
        if rows.empty:
            continue
        target = df.set_index(["district_id", "date"])
        keys = list(zip(rows["district_id"], rows["target_date"], strict=True))
        sub = target.reindex(keys).reset_index()
        rows["cams_raw"] = sub["cams_aqi"].to_numpy()
        # only past truth is visible: the frame is cut at t - 1 for lags, targets come later
        visible = df.assign(**{p: df[p].where(df["date"] < t) for p in POLLUTANTS})
        corr = bias.corrected_values(visible, t)
        rows = rows.merge(
            corr[["district_id", "target_date", "corrected_aqi"]].rename(
                columns={"corrected_aqi": "cams_corrected"}
            ),
            on=["district_id", "target_date"],
            how="left",
        )
        rows["persistence"] = rows["lag1"]
        rows["climatology"] = [clim.get((d, td.month), np.nan) for d, td in keys]
        if outlook is not None:
            q = outlook.predict(rows)
            rows["outlook"], rows["outlook_low"], rows["outlook_high"] = (
                q["mid"],
                q["low"],
                q["high"],
            )
        preds.append(rows)
    allp = pd.concat(preds, ignore_index=True)
    lines = []
    for lead, g in allp.groupby("lead"):
        methods = (
            ["cams_corrected", "cams_raw", "persistence"]
            if lead <= 5
            else ["outlook", "persistence", "climatology"]
        )
        for m in methods:
            if m in g:
                n, mae, hit = _score(g[m], g["y"])
                lines.append({"day": int(lead), "method": m, "n": n, "mae": mae, "hit_rate": hit})
    cov = None
    if "outlook_low" in allp:
        o = allp[(allp["lead"] >= 6) & allp["y"].notna() & allp["outlook_low"].notna()]
        cov = float(((o["y"] >= o["outlook_low"]) & (o["y"] <= o["outlook_high"])).mean())
    return Backtest(pd.DataFrame(lines), cov, len(preds), issues[0], issues[-1])


def summary(bt: Backtest) -> dict:
    """Average MAE per method over days 1-5 and 6-10, and the beats-baseline verdicts."""
    t = bt.table
    early, late = t[t["day"] <= 5], t[t["day"] >= 6]
    m = lambda frame, name: float(frame[frame["method"] == name]["mae"].mean())  # noqa: E731
    out = {
        "days_1_5": {k: m(early, k) for k in ("cams_corrected", "cams_raw", "persistence")},
        "days_6_10": {k: m(late, k) for k in ("outlook", "persistence", "climatology")},
        "coverage_80": bt.coverage_80,
        "issues": bt.issues,
    }
    d15, d610 = out["days_1_5"], out["days_6_10"]
    out["bias_beats_baseline"] = bool(
        d15["cams_corrected"] < d15["cams_raw"] and d15["cams_corrected"] < d15["persistence"]
    )
    out["outlook_beats_baseline"] = bool(
        d610["outlook"] < d610["persistence"] and d610["outlook"] < d610["climatology"]
    )
    return out


def report_markdown(bt: Backtest, s: dict, names: dict[int, str] | None = None) -> str:
    pivot_mae = bt.table.pivot(index="day", columns="method", values="mae")
    pivot_hit = bt.table.pivot(index="day", columns="method", values="hit_rate")
    order = ["cams_corrected", "cams_raw", "outlook", "persistence", "climatology"]
    cols = [c for c in order if c in pivot_mae.columns]
    label = {
        "cams_corrected": "Corrected CAMS",
        "cams_raw": "Raw CAMS",
        "outlook": "Outlook (median)",
        "persistence": "Tomorrow = today",
        "climatology": "Month average",
    }
    lines = [
        "# AQI forecast backtest",
        "",
        f"Rolling backtest: {bt.issues} weekly issue dates from {bt.start} to {bt.end}; models are",
        "retrained before every issue date on data available then. Target: daily city AQI",
        "(India AQI, sub-index of daily mean concentrations, mean over stations).",
        "Day 1 = issue date (today), day L = issue + L - 1.",
        "",
        "## MAE (AQI points) per day ahead",
        "",
        "| Day | " + " | ".join(label[c] for c in cols) + " |",
        "| --- |" + " --- |" * len(cols),
    ]
    for day, r in pivot_mae.iterrows():
        best = r[cols].astype(float).idxmin()
        cells = [
            ("**%.1f**" if c == best else "%.1f") % r[c] if pd.notna(r[c]) else "–" for c in cols
        ]
        lines.append(f"| {day} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Category hit rate (same CPCB category as the truth)",
        "",
        "| Day | " + " | ".join(label[c] for c in cols) + " |",
        "| --- |" + " --- |" * len(cols),
    ]
    for day, r in pivot_hit.iterrows():
        lines.append(
            f"| {day} | "
            + " | ".join(f"{r[c] * 100:.0f}%" if pd.notna(r[c]) else "–" for c in cols)
            + " |"
        )
    d15, d610 = s["days_1_5"], s["days_6_10"]
    lines += [
        "",
        "## Verdict",
        "",
        f"- Days 1–5: corrected CAMS MAE {d15['cams_corrected']:.1f} vs raw CAMS "
        f"{d15['cams_raw']:.1f} and tomorrow = today {d15['persistence']:.1f} → "
        f"**{'beats' if s['bias_beats_baseline'] else 'does NOT beat'} both baselines**.",
        f"- Days 6–10: outlook MAE {d610['outlook']:.1f} vs tomorrow = today "
        f"{d610['persistence']:.1f} and month average {d610['climatology']:.1f} → "
        f"**{'beats' if s['outlook_beats_baseline'] else 'does NOT beat'} both baselines**.",
        f"- Outlook range (5–95% quantile models) contains the truth "
        f"{s['coverage_80'] * 100:.0f}% of the time (target: at least 80%)."
        if s["coverage_80"] is not None
        else "",
        "",
        "## Limits (read before trusting these numbers)",
        "",
        "- The CAMS archive holds analyses, not past forecasts: days 1–5 use CAMS at lead 0 for",
        "  every day, so their skill here is an upper bound; real forecasts will do worse.",
        "- The outlook uses observed (reanalysis) weather for target days; live serving uses the",
        "  weather forecast, so real skill is lower.",
        "- Raw CAMS has no free forecast beyond day 5, so days 6–10 compare against tomorrow =",
        "  today and the city's month average instead.",
        "- Truth is computed from OpenAQ daily means of CPCB/SPCB monitors (sub-index of daily",
        "  means); it tracks CPCB's published AQI but is not identical to it.",
    ]
    return "\n".join(x for x in lines if x is not None) + "\n"
