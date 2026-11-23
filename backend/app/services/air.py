"""Air-tab queries. All values come from stored data; nothing is guessed."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.analysis.aqi import category, sub_index, window_average, window_sub_index
from app.analysis.shadow import Neighbour, haversine_km, idw_estimate
from app.analysis.summary import AQI_POLLUTANTS, SETTLE_HOURS, floor_ist_hour
from app.analysis.time import IST, day_bounds, ist_date
from app.models import CityHourAqi, DailyCitySummary, District

LOOKBACK_FOR_NOW = timedelta(hours=6)


def _cat(aqi: int | None) -> tuple[str | None, str | None]:
    c = category(aqi)
    return (c[0], c[1]) if c else (None, None)


def hour_rows(session: Session, district_id: int, start: datetime, end: datetime):
    return (
        session.execute(
            select(CityHourAqi)
            .where(
                CityHourAqi.district_id == district_id,
                CityHourAqi.hour >= start,
                CityHourAqi.hour < end,
            )
            .order_by(CityHourAqi.hour)
        )
        .scalars()
        .all()
    )


def latest_summary(session: Session, district_id: int, day: date):
    return session.execute(
        select(DailyCitySummary).where(
            DailyCitySummary.district_id == district_id, DailyCitySummary.date == day
        )
    ).scalar()


def air_now(session: Session, district: District, now: datetime) -> dict:
    """Best available current AQI: CPCB official, else our measured, else CAMS estimate."""
    end = floor_ist_hour(now)  # only hours that have ended; the current hour is still open
    rows = hour_rows(session, district.id, end - LOOKBACK_FOR_NOW, end)
    pick = None
    for kind in ("official", "measured", "cams"):
        for row in reversed(rows):
            if getattr(row, f"{kind}_aqi") is not None:
                pick = (kind, row)
                break
        if pick:
            break
    shadow_row = next((r for r in reversed(rows) if r.shadow_aqi is not None), None)
    summary = latest_summary(session, district.id, ist_date(now))
    if pick is None:
        aqi = main = hour = None
        kind = None
    else:
        kind, row = pick
        aqi = getattr(row, f"{kind}_aqi")
        main = getattr(row, f"{kind}_main_pollutant")
        hour = row.hour
    name, key = _cat(aqi)
    return {
        "aqi": aqi,
        "category": name,
        "category_key": key,
        "main_pollutant": main,
        "aqi_kind": kind,  # official | measured | cams
        "hour": hour,
        "stations_reporting": getattr(pick[1], f"{kind}_stations", None) if pick else None,
        "completeness_pct": summary.completeness_pct if summary else None,
        "shadow_aqi": shadow_row.shadow_aqi if shadow_row else None,
        "shadow_aqi_low": shadow_row.shadow_aqi_low if shadow_row else None,
        "shadow_aqi_high": shadow_row.shadow_aqi_high if shadow_row else None,
        "shadow_hour": shadow_row.hour if shadow_row else None,
    }


def air_hourly(session: Session, district: District, now: datetime) -> list[dict]:
    """Today's IST hours: official / shadow (past) and CAMS forecast (future)."""
    start, end = day_bounds(ist_date(now))
    by_hour = {r.hour: r for r in hour_rows(session, district.id, start, end)}
    current = floor_ist_hour(now)
    out = []
    for hour in pd.date_range(start, end, freq="1h", inclusive="left"):
        h = hour.to_pydatetime()
        r = by_hour.get(h)
        is_future = h >= current
        official = r.official_aqi if r else None
        shadow = r.shadow_aqi if r else None
        forecast = r.cams_aqi if (r and is_future) else None
        out.append(
            {
                "hour": h,
                "official_aqi": official,
                "shadow_aqi": shadow,
                "shadow_aqi_low": r.shadow_aqi_low if r else None,
                "shadow_aqi_high": r.shadow_aqi_high if r else None,
                "estimated_aqi": r.cams_aqi if r and official is None and not is_future else None,
                "forecast_aqi": forecast,
                "is_forecast": is_future,
                "official_missing": (not is_future) and official is None,
            }
        )
    return out


OUTLOOK_DAYS = 5  # days 6-10 need the Phase 8 outlook model


def air_daily(session: Session, district: District, now: datetime) -> list[dict]:
    today = ist_date(now)
    start = day_bounds(today)[0]
    rows = hour_rows(session, district.id, start, start + timedelta(days=10))
    df = pd.DataFrame(
        [(ist_date(r.hour), r.official_aqi, r.cams_aqi) for r in rows],
        columns=["day", "official", "cams"],
    )
    out = []
    for i in range(10):
        day = today + timedelta(days=i)
        if i >= OUTLOOK_DAYS:
            out.append({"date": day, "low": None, "high": None, "is_outlook": True,
                        "available": False, "label": "estimated"})  # fmt: skip
            continue
        values = df[df["day"] == day]["cams"].dropna() if not df.empty else pd.Series()
        enough = len(values) >= 12
        out.append(
            {
                "date": day,
                "low": int(values.min()) if enough else None,
                "high": int(values.max()) if enough else None,
                "is_outlook": False,
                "available": enough,
                "label": "estimated",
            }
        )
    return out


def air_monthly(session: Session, district: District, now: datetime) -> list[dict]:
    """Last 12 months: mean of daily AQI (our measured, else CPCB official)."""
    first = (ist_date(now).replace(day=1) - pd.DateOffset(months=11)).date()
    rows = session.execute(
        select(
            DailyCitySummary.date, DailyCitySummary.measured_aqi, DailyCitySummary.official_aqi
        ).where(DailyCitySummary.district_id == district.id, DailyCitySummary.date >= first)
    ).all()
    df = pd.DataFrame(rows, columns=["date", "measured", "official"])
    out = []
    for i in range(12):
        month = (pd.Timestamp(first) + pd.DateOffset(months=i)).date()
        if df.empty:
            sel = pd.Series(dtype=float)
        else:
            m = df[pd.to_datetime(df["date"]).dt.to_period("M") == pd.Period(month, "M")]
            sel = m["measured"].fillna(m["official"]).dropna()
        out.append(
            {
                "month": month.strftime("%Y-%m"),
                "avg_aqi": int(round(sel.mean())) if len(sel) else None,
                "days": int(len(sel)),
                "is_current": i == 11,
            }
        )
    return out


UNITS = {"co": "mg/m3"}


def air_pollutants(session: Session, district: District, now: datetime) -> dict:
    """24-h (8-h for CO/O3) values per pollutant: stations if any, else CAMS model."""
    # Station data reaches OpenAQ 1-2 h late: average over settled hours only.
    end = floor_ist_hour(now - timedelta(hours=SETTLE_HOURS))
    start = end - timedelta(hours=24)
    rows = session.execute(
        text(
            "SELECT r.station_id, r.hour, r.pollutant, r.value FROM readings r"
            " JOIN stations s ON s.id = r.station_id WHERE s.district_id = :d"
            " AND s.source = 'openaq' AND s.is_reference AND r.status = 'ok'"
            " AND r.hour >= :s AND r.hour < :e"
        ),
        {"d": district.id, "s": start, "e": end},
    ).all()
    df = pd.DataFrame(rows, columns=["station_id", "hour", "pollutant", "value"])
    model = session.execute(
        text(
            "SELECT hour, pollutant, value FROM model_air WHERE district_id = :d"
            " AND hour >= :s AND hour < :e AND value IS NOT NULL"
        ),
        {"d": district.id, "s": start, "e": end + timedelta(hours=1)},
    ).all()
    mdf = pd.DataFrame(model, columns=["hour", "pollutant", "value"])
    for frame in (df, mdf):
        if not frame.empty:
            frame["hour"] = pd.to_datetime(frame["hour"], utc=True)
    out = []
    for pollutant in AQI_POLLUTANTS:
        entry = {"pollutant": pollutant, "unit": UNITS.get(pollutant, "ug/m3"), "value": None,
                 "sub_index": None, "label": None, "stations": 0}  # fmt: skip
        st = df[df["pollutant"] == pollutant] if not df.empty else df
        values, subs = [], []
        for _, g in st.groupby("station_id") if len(st) else []:
            series = g.set_index("hour")["value"]
            avg = window_average(series, pollutant, end)
            si = window_sub_index(series, pollutant, end)
            if avg is not None and si is not None:
                values.append(avg)
                subs.append(si)
        if values:
            entry.update(value=round(sum(values) / len(values), 2),
                         sub_index=round(sum(subs) / len(subs)), label="measured",
                         stations=len(values))  # fmt: skip
        elif not mdf.empty:
            mg = mdf[mdf["pollutant"] == pollutant]
            if len(mg):
                series = mg.groupby("hour")["value"].mean()
                avg = window_average(series, pollutant, end)
                if avg is not None:
                    entry.update(value=round(avg, 2), sub_index=round(sub_index(pollutant, avg)),
                                 label="estimated")  # fmt: skip
        out.append(entry)
    co2 = None
    if not mdf.empty:
        c = mdf[mdf["pollutant"] == "co2"].sort_values("hour")
        if len(c):
            co2 = {"value": round(float(c["value"].iloc[-1]), 1), "unit": "ppm",
                   "hour": c["hour"].iloc[-1].to_pydatetime(), "label": "estimated",
                   "note": "Context only: CO2 is not part of India's AQI."}  # fmt: skip
    return {"pollutants": out, "co2": co2, "window_end": end}


def air_stations(session: Session, district: District, now: datetime) -> dict:
    """CPCB station pins at the latest snapshot hour: measured, estimated or silent."""
    stations = session.execute(
        text(
            "SELECT id, name, lat, lon, last_seen_at FROM stations WHERE district_id = :d"
            " AND source = 'cpcb' AND is_active AND lat IS NOT NULL"
        ),
        {"d": district.id},
    ).all()
    if not stations:
        return {"hour": None, "stations": []}
    ids = [s.id for s in stations]
    latest = session.execute(
        text("SELECT max(hour) FROM readings WHERE station_id = ANY(:ids) AND hour <= :n"),
        {"ids": ids, "n": now},
    ).scalar()
    vals = session.execute(
        text(
            "SELECT station_id, pollutant, value, status FROM readings"
            " WHERE station_id = ANY(:ids) AND hour = :h"
        ),
        {"ids": ids, "h": latest},
    ).all()
    aqi: dict[int, tuple[float, str]] = {}
    for v in vals:
        if v.status == "ok" and (v.station_id not in aqi or v.value > aqi[v.station_id][0]):
            aqi[v.station_id] = (v.value, v.pollutant)
    pins = []
    for s in stations:
        if s.id in aqi:
            value, main = aqi[s.id]
            pins.append(
                {"id": s.id, "name": s.name, "lat": s.lat, "lon": s.lon, "aqi": round(value),
                 "main_pollutant": main, "status": "measured", "last_seen_at": s.last_seen_at}
            )  # fmt: skip
            continue
        nbs = [
            Neighbour(haversine_km(s.lat, s.lon, o.lat, o.lon), aqi[o.id][0])
            for o in stations
            if o.id in aqi
        ]
        est = idw_estimate(nbs)
        pins.append({"id": s.id, "name": s.name, "lat": s.lat, "lon": s.lon,
                     "aqi": round(est) if est is not None else None, "main_pollutant": None,
                     "status": "estimated" if est is not None else "silent",
                     "last_seen_at": s.last_seen_at})  # fmt: skip
    for p in pins:
        p["category"], p["category_key"] = _cat(p["aqi"])
    return {"hour": latest, "stations": pins}


def hour_label_ist(ts: datetime) -> str:
    return ts.astimezone(IST).strftime("%H:%M")
