"""Driving routes: OpenRouteService when ORS_API_KEY is set, else the public OSRM server.

Both use OpenStreetMap data. Results are cached for a day (routes rarely change), which also
keeps us well inside the public servers' fair-use limits.
"""

from __future__ import annotations

import httpx

from app.config import get_settings

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{a};{b}"
ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"


def parse_point(raw: str) -> tuple[float, float]:
    lat, lon = (float(v) for v in raw.split(","))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("bad coordinates")
    return round(lat, 4), round(lon, 4)


def route(http: httpx.Client, a: tuple[float, float], b: tuple[float, float]) -> dict:
    key = get_settings().ors_api_key
    if key:
        r = http.post(
            ORS_URL,
            json={"coordinates": [[a[1], a[0]], [b[1], b[0]]]},
            headers={"Authorization": key},
        )
        r.raise_for_status()
        feat = r.json()["features"][0]
        summary = feat["properties"]["summary"]
        coords = feat["geometry"]["coordinates"]
        source = "OpenRouteService (© OpenStreetMap contributors)"
        distance, duration = summary["distance"], summary["duration"]
    else:
        r = http.get(
            OSRM_URL.format(a=f"{a[1]},{a[0]}", b=f"{b[1]},{b[0]}"),
            params={"overview": "simplified", "geometries": "geojson"},
        )
        r.raise_for_status()
        body = r.json()
        if body.get("code") != "Ok" or not body.get("routes"):
            raise ValueError(f"no route: {body.get('code')}")
        best = body["routes"][0]
        coords = best["geometry"]["coordinates"]
        source = "OSRM (© OpenStreetMap contributors)"
        distance, duration = best["distance"], best["duration"]
    return {
        "distance_km": round(distance / 1000, 1),
        "duration_min": int(round(duration / 60)),
        "geometry": [[round(lat, 5), round(lon, 5)] for lon, lat in coords],
        "source": source,
    }
