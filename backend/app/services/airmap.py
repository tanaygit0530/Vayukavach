"""PM2.5 grid for the map layer: CAMS model values from Open-Meteo for a grid of points."""

from __future__ import annotations

import httpx

from app.analysis.aqi import category, sub_index

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
# Open-Meteo counts every point as one call (free tier ~10,000/day). 5 x 5 = 25 per grid;
# the frontend asks for a fixed box per district, so the 1-hour cache is shared by everyone.
GRID = 5
MAX_SPAN_DEG = 12.0


def parse_bbox(raw: str) -> tuple[float, float, float, float]:
    """'minLon,minLat,maxLon,maxLat' -> rounded tuple (rounding makes cache hits likely)."""
    parts = [float(x) for x in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox needs 4 numbers: minLon,minLat,maxLon,maxLat")
    w, s, e, n = parts
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ValueError("bbox out of range or min >= max")
    if e - w > MAX_SPAN_DEG or n - s > MAX_SPAN_DEG:
        raise ValueError(f"bbox larger than {MAX_SPAN_DEG} degrees")
    return tuple(round(v, 2) for v in (w, s, e, n))  # type: ignore[return-value]


def grid_points(bbox: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    w, s, e, n = bbox
    step_x, step_y = (e - w) / (GRID - 1), (n - s) / (GRID - 1)
    return [
        (round(s + j * step_y, 4), round(w + i * step_x, 4))
        for j in range(GRID)
        for i in range(GRID)
    ]


def fetch_grid(http: httpx.Client, bbox: tuple[float, float, float, float]) -> dict:
    points = grid_points(bbox)
    response = http.get(
        AIR_URL,
        params={
            "latitude": ",".join(str(p[0]) for p in points),
            "longitude": ",".join(str(p[1]) for p in points),
            "current": "pm2_5",
            "timezone": "Asia/Kolkata",
        },
    )
    response.raise_for_status()
    payload = response.json()
    payload = payload if isinstance(payload, list) else [payload]
    cells, time = [], None
    for (lat, lon), loc in zip(points, payload, strict=True):
        current = loc.get("current") or {}
        time = time or current.get("time")
        pm25 = current.get("pm2_5")
        si = sub_index("pm25", pm25) if pm25 is not None else None
        cat = category(si) if si is not None else None
        cells.append(
            {
                "lat": lat,
                "lon": lon,
                "pm25": pm25,
                "pm25_sub_index": round(si) if si else None,
                "category_key": cat[1] if cat else None,
            }  # fmt: skip
        )
    return {"cells": cells, "time_ist": time, "grid": GRID}
