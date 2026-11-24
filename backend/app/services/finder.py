"""Clean Air and Cool Places Finder (spec Module 4).

Every suggestion rests on a real value; a place with no data is never returned.
- Cleaner air: CPCB stations with a recent reading (hour start within 4.5 h: feed lag + hourly
  fetch; Measured), plus a 3-day CAMS outlook for the shortlisted places (Estimated). Ranked by
  0.6 x current + 0.4 x outlook.
- Cooler places: hill stations and towns with CPCB stations, ranked by the Open-Meteo 3-day mean
  of the daily "feels like" maximum (Estimated). Park-level cooling needs satellite land-surface
  temperature, which VayuKavach does not have yet, so "nearby" heat returns no places.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.analysis import heat as heatcalc
from app.analysis.aqi import aqi_from_concentrations, category
from app.analysis.shadow import haversine_km
from app.models import District
from app.services.air import air_now
from app.services.reference import CPCB_HEALTH, CPCB_HEALTH_SOURCE

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
HILLS = Path(__file__).resolve().parents[1] / "data" / "hill_stations.csv"

RADIUS = {"nearby": 10.0, "daytrip": 150.0, "vacation": None}
MIN_DISTANCE = {"nearby": 0.0, "daytrip": 10.0, "vacation": 10.0}  # skip what "nearby" covers
# Measured from the hour's start: 1 h averaging + CPCB feed lag (~1-2 h) + hourly fetch.
FRESH = timedelta(hours=4, minutes=30)
TOP = 10
SHORTLIST = 25  # places that get a forecast lookup (Open-Meteo counts each point)
VACATION_TOWNS = 30
ROAD_FACTOR = 1.3  # road distance / straight line, for the list's rough travel time


class FinderError(ValueError):
    pass


@dataclass(frozen=True)
class Origin:
    name: str
    lat: float
    lon: float
    district: District | None


def resolve_origin(session: Session, raw: str) -> Origin:
    """`from` is a district id (e.g. delhi) or 'lat,lon'."""
    if "," in raw:
        try:
            lat, lon = (float(v) for v in raw.split(","))
        except ValueError as exc:
            raise FinderError("from must be a district id or 'lat,lon'") from exc
        if not (6 <= lat <= 37.5 and 68 <= lon <= 98):
            raise FinderError("location is outside India")
        return Origin("Your location", lat, lon, None)
    district = session.execute(select(District).where(District.slug == raw.lower())).scalar()
    if district is None:
        raise FinderError(f"unknown place '{raw}'")
    return Origin(district.name, district.lat, district.lon, district)


def approx_minutes(km: float, mode: str) -> int:
    speed = 25.0 if mode == "nearby" else 60.0  # km/h: city traffic vs highways (OSRM ~80)
    return max(5, int(round(km * ROAD_FACTOR / speed * 60 / 5) * 5))


def _within(places: list[dict], origin: Origin, mode: str) -> list[dict]:
    radius, floor = RADIUS[mode], MIN_DISTANCE[mode]
    out = []
    for p in places:
        d = haversine_km(origin.lat, origin.lon, p["lat"], p["lon"])
        if (radius is None or d <= radius) and d >= floor:
            out.append({**p, "distance_km": round(d, 1)})
    return out


# ---------------------------------------------------------------- cleaner air

LATEST_CPCB = text(
    """
    WITH last AS (
        SELECT DISTINCT ON (r.station_id) r.station_id, r.hour
        FROM readings r JOIN stations s ON s.id = r.station_id
        WHERE s.source = 'cpcb' AND s.is_active AND s.lat IS NOT NULL AND r.status = 'ok'
          AND r.unit = 'aqi_subindex' AND r.hour >= :since
        ORDER BY r.station_id, r.hour DESC
    )
    SELECT s.id, s.name, s.city, s.state, s.lat, s.lon, l.hour, max(r.value) AS aqi
    FROM last l
    JOIN readings r ON r.station_id = l.station_id AND r.hour = l.hour AND r.status = 'ok'
    JOIN stations s ON s.id = l.station_id
    GROUP BY s.id, s.name, s.city, s.state, s.lat, s.lon, l.hour
    HAVING count(*) >= 3 AND bool_or(r.pollutant IN ('pm25', 'pm10'))
    """
)


def cpcb_now(session: Session, now: datetime) -> list[dict]:
    rows = session.execute(LATEST_CPCB, {"since": now - FRESH}).mappings().all()
    return [
        {
            "id": f"station-{r['id']}",
            "name": r["name"].strip(),
            "city": r["city"],
            "state": r["state"],
            "lat": r["lat"],
            "lon": r["lon"],
            "value": int(round(r["aqi"])),
            "hour": r["hour"],
            "kind": "station",
        }
        for r in rows
    ]


def cams_outlook(http: httpx.Client, places: list[dict], days: int = 3) -> dict[str, list[dict]]:
    """India AQI from CAMS daily means for the next `days` days, per place (Estimated)."""
    if not places:
        return {}
    r = http.get(
        AIR_URL,
        params={
            "latitude": ",".join(f"{p['lat']:.4f}" for p in places),
            "longitude": ",".join(f"{p['lon']:.4f}" for p in places),
            "hourly": "pm2_5,pm10,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide,ozone",
            "forecast_days": days,
            "timezone": "Asia/Kolkata",
        },
    )
    r.raise_for_status()
    payload = r.json()
    payload = payload if isinstance(payload, list) else [payload]
    names = {
        "pm2_5": "pm25",
        "pm10": "pm10",
        "nitrogen_dioxide": "no2",
        "sulphur_dioxide": "so2",
        "carbon_monoxide": "co",
        "ozone": "o3",
    }
    out = {}
    for p, loc in zip(places, payload, strict=True):
        h = loc.get("hourly") or {}
        df = pd.DataFrame({names[k]: h.get(k) for k in names}, index=pd.to_datetime(h.get("time")))
        df = df.apply(pd.to_numeric, errors="coerce")
        df["co"] = df["co"] / 1000.0
        series = []
        for day, g in df.groupby(df.index.date):
            res = aqi_from_concentrations(g.mean().to_dict())
            if res.valid:
                series.append({"date": day, "value": res.aqi})
        out[p["id"]] = series
    return out


def find_cleaner_air(
    session: Session, http: httpx.Client, origin: Origin, mode: str, now: datetime
) -> dict:
    stations = cpcb_now(session, now)
    here = None
    if origin.district is not None:
        here = air_now(session, origin.district, now)["aqi"]
    if here is None:
        near = sorted(
            stations, key=lambda s: haversine_km(origin.lat, origin.lon, s["lat"], s["lon"])
        )
        if near and haversine_km(origin.lat, origin.lon, near[0]["lat"], near[0]["lon"]) <= 15:
            here = near[0]["value"]
    candidates = _within(stations, origin, mode)
    if mode != "nearby":  # one entry per town: its cleanest station
        best: dict[str, dict] = {}
        for c in candidates:
            key = (c["city"] or c["name"]).lower()
            if key not in best or c["value"] < best[key]["value"]:
                best[key] = c
        candidates = list(best.values())
        for c in candidates:
            c["name"] = c["city"] or c["name"]
            c["kind"] = "town"
    candidates.sort(key=lambda c: (c["value"], c["distance_km"]))
    shortlist = candidates[:SHORTLIST]
    outlook = cams_outlook(http, shortlist)
    places = []
    for c in shortlist:
        fc = outlook.get(c["id"], [])
        fc_mean = sum(f["value"] for f in fc) / len(fc) if fc else None
        score = 0.6 * c["value"] + 0.4 * fc_mean if fc_mean is not None else float(c["value"])
        cat = category(c["value"])
        places.append(
            {
                **{k: c[k] for k in ("id", "name", "state", "lat", "lon", "distance_km", "kind")},
                "approx_minutes": approx_minutes(c["distance_km"], mode),
                "value": c["value"],
                "unit": "AQI",
                "value_label": "measured",
                "value_source": "CPCB station, latest hour",
                "category": cat[0] if cat else None,
                "category_key": cat[1] if cat else None,
                "forecast": fc,
                "forecast_label": "estimated",
                "better_by": None if here is None else here - c["value"],
                "score": round(score, 1),
            }
        )
    places.sort(key=lambda p: (p["score"], p["distance_km"]))
    if here is not None:
        places = [p for p in places if p["value"] < here] or places[:0]
    return {"here_value": here, "places": places[:TOP]}


def air_precautions(here: int | None, dest: int | None) -> list[dict]:
    out = []
    for label, value in (("Where you are now", here), ("At the destination", dest)):
        cat = category(value)
        if cat:
            out.append(
                {
                    "for": label,
                    "text": f"{cat[0]}: {CPCB_HEALTH[cat[1]]}",
                    "source": CPCB_HEALTH_SOURCE,
                }
            )
    return out


# ---------------------------------------------------------------- cooler places


def hill_stations() -> list[dict]:
    with HILLS.open(newline="", encoding="utf-8") as f:
        return [
            {
                "id": f"hill-{r['name'].lower().replace(' ', '-')}",
                "name": r["name"],
                "state": r["state"],
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "kind": "hill_station",
                "elevation_m": int(r["elevation_m"]),
            }
            for r in csv.DictReader(f)
        ]


def station_towns(session: Session) -> list[dict]:
    rows = (
        session.execute(
            text(
                "SELECT city, state, avg(lat) AS lat, avg(lon) AS lon, count(*) AS n FROM stations"
                " WHERE source = 'cpcb' AND lat IS NOT NULL AND city IS NOT NULL"
                " GROUP BY city, state ORDER BY count(*) DESC"
            )
        )
        .mappings()
        .all()
    )
    return [
        {
            "id": f"town-{r['city'].lower().replace(' ', '-')}",
            "name": r["city"],
            "state": r["state"],
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "kind": "town",
            "stations": int(r["n"]),
        }
        for r in rows
    ]


def weather_outlook(http: httpx.Client, places: list[dict], days: int = 3) -> dict[str, list[dict]]:
    if not places:
        return {}
    r = http.get(
        WEATHER_URL,
        params={
            "latitude": ",".join(f"{p['lat']:.4f}" for p in places),
            "longitude": ",".join(f"{p['lon']:.4f}" for p in places),
            "daily": "temperature_2m_max,apparent_temperature_max,relative_humidity_2m_mean",
            "forecast_days": days,
            "timezone": "Asia/Kolkata",
        },
    )
    r.raise_for_status()
    payload = r.json()
    payload = payload if isinstance(payload, list) else [payload]
    out = {}
    for p, loc in zip(places, payload, strict=True):
        d = loc.get("daily") or {}
        rows = []
        for i, day in enumerate(d.get("time") or []):
            feels, tmax = d["apparent_temperature_max"][i], d["temperature_2m_max"][i]
            rh = d.get("relative_humidity_2m_mean", [None] * (i + 1))[i]
            if feels is None or tmax is None:
                continue
            rows.append(
                {
                    "date": day,
                    "value": round(feels, 1),
                    "temperature_max": round(tmax, 1),
                    "humidity": rh,
                }
            )
        out[p["id"]] = rows
    return out


COMFORT = (18.0, 27.0)  # feels-like band in degC used for ranking only


def comfort_gap(feels_like: float) -> float:
    lo, hi = COMFORT
    return (
        0.0 if lo <= feels_like <= hi else (lo - feels_like if feels_like < lo else feels_like - hi)
    )


def heat_level(day: dict | None) -> str | None:
    if not day or day.get("humidity") is None:
        return None
    t, rh = day["temperature_max"], day["humidity"]
    return heatcalc.level_for(heatcalc.heat_index_c(t, rh), heatcalc.wet_bulb_c(t, min(rh, 99)))


def find_cooler(session: Session, http: httpx.Client, origin: Origin, mode: str) -> dict:
    if mode == "nearby":
        return {
            "here_value": None,
            "places": [],
            "here_level": None,
            "empty_reason": "Park- and lake-level cooling needs satellite land-surface "
            "temperature, which VayuKavach does not have yet. Try a day trip.",
        }
    towns = station_towns(session)
    pool = hill_stations() + (towns if mode == "daytrip" else towns[:VACATION_TOWNS])
    candidates = sorted(_within(pool, origin, mode), key=lambda c: c["distance_km"])
    if mode == "vacation":  # all hill stations first, then the biggest towns
        candidates.sort(key=lambda c: (c["kind"] != "hill_station", c["distance_km"]))
    shortlist = candidates[: SHORTLIST * 2]
    origin_place = {"id": "origin", "lat": origin.lat, "lon": origin.lon}
    outlook = weather_outlook(http, [origin_place, *shortlist])
    here_days = outlook.get("origin", [])
    here = sum(d["value"] for d in here_days) / len(here_days) if here_days else None
    places = []
    for c in shortlist:
        fc = outlook.get(c["id"], [])
        if not fc:
            continue  # no data, never recommended
        mean = sum(f["value"] for f in fc) / len(fc)
        places.append(
            {
                **{k: c[k] for k in ("id", "name", "state", "lat", "lon", "distance_km", "kind")},
                "approx_minutes": approx_minutes(c["distance_km"], mode),
                "value": round(mean, 1),
                "unit": "°C feels-like (3-day mean of daily max)",
                "value_label": "estimated",
                "value_source": "Open-Meteo forecast",
                "category": heatcalc.LEVEL_NAMES.get(heat_level(fc[0]) or "", None),
                "category_key": heat_level(fc[0]),
                "forecast": [{"date": f["date"], "value": f["value"]} for f in fc],
                "forecast_label": "estimated",
                "better_by": None if here is None else round(here - mean, 1),
                "score": round(mean, 1),
            }
        )
    if here is not None:
        places = [p for p in places if p["better_by"] is not None and p["better_by"] >= 1.0]
    # Coldest is not best relief (e.g. a snowy valley in November): rank by how far the
    # feels-like is from a comfortable band, then by distance.
    for p in places:
        p["score"] = round(comfort_gap(p["value"]), 1)
    places.sort(key=lambda p: (p["score"], p["distance_km"]))
    return {
        "here_value": None if here is None else round(here, 1),
        "places": places[:TOP],
        "here_level": heat_level(here_days[0] if here_days else None),
    }


def heat_precautions(level: str | None) -> list[dict]:
    """NDMA heatwave guidance for the origin's heat level (official wording, no additions)."""
    return [
        {"for": "Travelling in heat", "text": t, "source": heatcalc.TIPS_SOURCE}
        for t in heatcalc.tips_for(level or "caution")
    ]
