"""The only data the chatbot may use (spec Module 5). Each tool wraps an existing service and
returns plain data plus `source`, `time` (IST) and `label` (measured / estimated). When there
is no data the result says `available: false` and the bot must say so, never guess."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import heat as heatcalc
from app.analysis.aqi import category
from app.analysis.time import IST, ist_date
from app.models import DailyCitySummary, District
from app.services import finder
from app.services.air import air_daily, air_now
from app.services.reference import CPCB_HEALTH, CPCB_HEALTH_SOURCE
from app.services.weather import heat_report

# Hindi / Marathi names of covered cities (Devanagari), so "दिल्ली" finds delhi.
NAMES = {
    "दिल्ली": "delhi",
    "देहली": "delhi",
    "मुंबई": "mumbai",
    "मुम्बई": "mumbai",
    "कोलकाता": "kolkata",
    "कलकत्ता": "kolkata",
    "चेन्नई": "chennai",
    "बेंगलुरु": "bengaluru",
    "बेंगळुरू": "bengaluru",
    "बंगलौर": "bengaluru",
    "बैंगलोर": "bengaluru",
    "हैदराबाद": "hyderabad",
    "पटना": "patna",
    "कानपुर": "kanpur",
    "लखनऊ": "lucknow",
    "शिमला": "shimla",
    "bangalore": "bengaluru",
    "bombay": "mumbai",
    "calcutta": "kolkata",
    "madras": "chennai",
    "new delhi": "delhi",
}

SRC_METHODS = "VayuKavach methods (docs/SPEC.md, Key methods)"


@dataclass
class ToolContext:
    session: Session
    now: datetime
    http: httpx.Client | None = None
    calls: list[dict] = field(default_factory=list)  # every call and its result, for sources


def find_district(session: Session, place: str | None) -> District | None:
    if not place:
        return None
    key = place.strip().lower()
    key = NAMES.get(place.strip(), NAMES.get(key, key))
    return session.execute(
        select(District).where((District.slug == key) | (District.name.ilike(key)))
    ).scalar()


def parse_day(raw: str | None, now: datetime) -> date:
    today = ist_date(now)
    s = (raw or "today").strip().lower()
    if s in {"today", "now", "आज"}:
        return today
    if s in {"yesterday", "बीता कल", "काल"}:
        return today - timedelta(days=1)
    if s in {"tomorrow", "कल", "उद्या"}:
        return today + timedelta(days=1)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return date.fromisoformat(s)
    return today


def _ist(ts: datetime | None) -> str | None:
    return ts.astimezone(IST).strftime("%d %b %Y, %H:%M IST") if ts else None


def _no_data(tool: str, place: str | None, reason: str) -> dict:
    return {
        "tool": tool,
        "available": False,
        "place": place,
        "reason": reason,
        "source": None,
        "time": None,
        "label": None,
    }


def _covered(ctx: ToolContext, tool: str, place: str | None):
    d = find_district(ctx.session, place)
    if d is None:
        return None, _no_data(tool, place, "VayuKavach does not cover this place yet")
    return d, None


def get_aqi(ctx: ToolContext, place: str, date: str = "today") -> dict:
    d, miss = _covered(ctx, "get_aqi", place)
    if miss:
        return miss
    day = parse_day(date, ctx.now)
    if day == ist_date(ctx.now):
        now = air_now(ctx.session, d, ctx.now)
        if now["aqi"] is None:
            return _no_data("get_aqi", d.name, "no AQI reading in the last 6 hours")
        kind = now["aqi_kind"]
        return {
            "tool": "get_aqi",
            "available": True,
            "place": d.name,
            "date": str(day),
            "aqi": now["aqi"],
            "category": now["category"],
            "main_pollutant": now["main_pollutant"],
            "source": {
                "official": "CPCB via data.gov.in",
                "measured": "CPCB/SPCB stations via OpenAQ",
                "cams": "CAMS model via Open-Meteo",
            }[kind],
            "time": _ist(now["hour"] + timedelta(hours=1) if now["hour"] else None),
            "label": "estimated" if kind == "cams" else "measured",
        }
    s = _summary(ctx, d, day)
    value = (s.official_aqi or s.measured_aqi) if s else None
    if value is None:
        return _no_data("get_aqi", d.name, f"no stored AQI for {day}")
    cat = category(value)
    return {
        "tool": "get_aqi",
        "available": True,
        "place": d.name,
        "date": str(day),
        "aqi": value,
        "category": cat[0] if cat else None,
        "main_pollutant": s.measured_main_pollutant,
        "source": "CPCB via data.gov.in" if s.official_aqi else "CPCB/SPCB stations via OpenAQ",
        "time": _ist(s.computed_at),
        "label": "measured",
    }


def _summary(ctx: ToolContext, d: District, day: date) -> DailyCitySummary | None:
    return ctx.session.execute(
        select(DailyCitySummary).where(
            DailyCitySummary.district_id == d.id, DailyCitySummary.date == day
        )
    ).scalar()


def get_completeness(ctx: ToolContext, place: str, date: str = "today") -> dict:
    d, miss = _covered(ctx, "get_completeness", place)
    if miss:
        return miss
    day = parse_day(date, ctx.now)
    s = _summary(ctx, d, day)
    if s is None or s.completeness_pct is None:
        return _no_data("get_completeness", d.name, f"no station completeness data for {day}")
    return {
        "tool": "get_completeness",
        "available": True,
        "place": d.name,
        "date": str(day),
        "completeness_pct": s.completeness_pct,
        "stations": s.stations_total,
        "stations_silent_3h": s.stations_silent,
        "city_silent_hours": s.city_silent_hours,
        "missing_when_it_mattered_flag": s.gap_bias_flag,
        "polluted_hours_missing_pct": s.polluted_missing_pct,
        "clean_hours_missing_pct": s.clean_missing_pct,
        "partial_day": s.is_partial_day,
        "source": "CPCB/SPCB stations via OpenAQ",
        "time": _ist(s.computed_at),
        "label": "measured",
    }


def get_shadow_aqi(ctx: ToolContext, place: str, date: str = "today") -> dict:
    d, miss = _covered(ctx, "get_shadow_aqi", place)
    if miss:
        return miss
    day = parse_day(date, ctx.now)
    s = _summary(ctx, d, day)
    if day == ist_date(ctx.now):
        now = air_now(ctx.session, d, ctx.now)
        shadow, lo, hi = now["shadow_aqi"], now["shadow_aqi_low"], now["shadow_aqi_high"]
        official = now["aqi"] if now["aqi_kind"] == "official" else None
        when = now["shadow_hour"]
    else:
        shadow, lo, hi = (s.shadow_aqi, s.shadow_aqi_low, s.shadow_aqi_high) if s else (None,) * 3
        official, when = (s.official_aqi if s else None), (s.computed_at if s else None)
    if shadow is None:
        return _no_data("get_shadow_aqi", d.name, "no shadow estimate (needs station history)")
    return {
        "tool": "get_shadow_aqi",
        "available": True,
        "place": d.name,
        "date": str(day),
        "shadow_aqi": shadow,
        "band_low": lo,
        "band_high": hi,
        "official_aqi": official,
        "completeness_pct": s.completeness_pct if s else None,
        "validation_error_pm25_ugm3": s.shadow_mae_pm25 if s else None,
        "method": "missing station-hours filled from stations within 15 km (inverse-distance "
        "weighting); band = error measured on hidden real readings",
        "source": "VayuKavach shadow estimate from CPCB/SPCB stations",
        "time": _ist(when),
        "label": "estimated",
    }


def get_forecast(ctx: ToolContext, place: str, days: int = 3) -> dict:
    d, miss = _covered(ctx, "get_forecast", place)
    if miss:
        return miss
    # at least today + tomorrow: with days=1 a model asked about "tomorrow" saw only today
    days = max(2, min(int(days or 3), 10))
    aq = [x for x in air_daily(ctx.session, d, ctx.now)[:days] if x["available"]]
    heat = heat_report(ctx.session, d, ctx.now)["daily"][:days]
    if not aq and not heat:
        return _no_data("get_forecast", d.name, "no forecast stored")
    today = ist_date(ctx.now)

    def rel(day) -> str:
        """today / tomorrow / in N days, so a model cannot mislabel the dates."""
        n = (date.fromisoformat(str(day)) - today).days
        return {0: "today", 1: "tomorrow"}.get(n, f"in {n} days")

    return {
        "tool": "get_forecast",
        "available": True,
        "place": d.name,
        "today": str(today),
        "aqi": [
            {
                "date": str(x["date"]),
                "day": rel(x["date"]),
                "low": x["low"],
                "high": x["high"],
                "most_likely": x["median"],
                "method": x["method"],
            }
            for x in aq
        ],
        "heat": [
            {
                "date": str(x["date"]),
                "day": rel(x["date"]),
                "temp_max": x["temperature_max"],
                "level": x["level"],
            }
            for x in heat
        ],
        "source": "VayuKavach AQI forecast (CAMS, corrected) and Open-Meteo weather",
        "time": _ist(ctx.now),
        "label": "estimated",
    }


def get_heat_risk(ctx: ToolContext, place: str, date: str = "today") -> dict:
    d, miss = _covered(ctx, "get_heat_risk", place)
    if miss:
        return miss
    r = heat_report(ctx.session, d, ctx.now)
    if r["level"] is None:
        return _no_data("get_heat_risk", d.name, "no weather data for this hour")
    return {
        "tool": "get_heat_risk",
        "available": True,
        "place": d.name,
        "feels_like_c": r["feels_like"],
        "heat_index_c": r["heat_index"],
        "wet_bulb_c": r["wet_bulb"],
        "level": r["level_name"],
        "worst_level_today": r["worst_level_today"],
        "instruction": r["instruction"],
        "safe_work_windows": [
            f"{w['from_hour']}:00-{w['to_hour']}:00" for w in r["safe_work_windows"]
        ],
        "thresholds": r["thresholds_status"],
        "source": "Open-Meteo weather; heat index (NWS), wet-bulb (Stull 2011)",
        "time": _ist(r["fetched_at"]),
        "label": "estimated",
    }


def find_places(
    ctx: ToolContext, goal: str = "air", mode: str = "daytrip", from_place: str | None = None
) -> dict:
    d, miss = _covered(ctx, "find_places", from_place)
    if miss:
        return miss
    if ctx.http is None:
        return _no_data("find_places", d.name, "finder unavailable")
    goal = "heat" if goal == "heat" else "air"
    mode = mode if mode in finder.RADIUS else "daytrip"
    origin = finder.Origin(d.name, d.lat, d.lon, d)
    data = (
        finder.find_cleaner_air(ctx.session, ctx.http, origin, mode, ctx.now)
        if goal == "air"
        else finder.find_cooler(ctx.session, ctx.http, origin, mode)
    )
    if not data["places"]:
        return _no_data("find_places", d.name, data.get("empty_reason") or "no better place found")
    return {
        "tool": "find_places",
        "available": True,
        "from": d.name,
        "goal": goal,
        "mode": mode,
        "here": data["here_value"],
        "places": [
            {
                "name": p["name"],
                "state": p["state"],
                "distance_km": p["distance_km"],
                "value": p["value"],
                "label": p["value_label"],
            }
            for p in data["places"][:3]
        ],
        "source": "CPCB stations (measured) + CAMS outlook"
        if goal == "air"
        else "Open-Meteo forecast",
        "time": _ist(ctx.now),
        "label": "measured" if goal == "air" else "estimated",
    }


def get_precautions(ctx: ToolContext, level: str) -> dict:
    key = (level or "").strip().lower().replace(" ", "").replace("_", "")
    if key in CPCB_HEALTH:
        return {
            "tool": "get_precautions",
            "available": True,
            "level": level,
            "advice": [CPCB_HEALTH[key]],
            "source": CPCB_HEALTH_SOURCE,
            "time": None,
            "label": None,
        }
    if key in heatcalc.LEVELS:
        return {
            "tool": "get_precautions",
            "available": True,
            "level": level,
            "advice": heatcalc.tips_for(key),
            "source": heatcalc.TIPS_SOURCE,
            "time": None,
            "label": None,
        }
    return _no_data("get_precautions", None, f"unknown level '{level}'")


TOOLS = {
    f.__name__: f
    for f in (
        get_aqi,
        get_completeness,
        get_shadow_aqi,
        get_forecast,
        get_heat_risk,
        find_places,
        get_precautions,
    )
}


def call(ctx: ToolContext, name: str, args: dict) -> dict:
    """Run a tool by name (LLM or rule engine). Unknown tools and bad arguments become
    `available: false`, never an exception the model could read as instructions."""
    fn = TOOLS.get(name)
    if fn is None:
        result = _no_data(name, None, "unknown tool")
    else:
        try:
            result = fn(ctx, **{k: v for k, v in (args or {}).items() if v is not None})
        except TypeError:
            result = _no_data(name, None, "bad arguments")
        except Exception:  # noqa: BLE001 - a failing data source must not break the chat
            logging.getLogger("vayukavach.chat").exception("tool %s failed", name)
            ctx.session.rollback()
            result = _no_data(name, None, "the data source is unavailable right now")
    ctx.calls.append(result)
    return result
