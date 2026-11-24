from datetime import timedelta

import httpx
import pytest
from sqlalchemy import text

from app.api.common import cache, get_http
from app.main import app
from app.services.finder import approx_minutes, comfort_gap
from tests.api.conftest import NOW, assert_meta

# (name, city, lat, lon, aqi) around Delhi (28.61, 77.21) and one far town
STATIONS = [
    ("Near Clean", "Delhi", 28.63, 77.22, 120),
    ("Near Dirty", "Delhi", 28.60, 77.20, 330),
    ("Town A 1", "Rewari", 28.19, 76.62, 90),
    ("Town A 2", "Rewari", 28.20, 76.63, 70),  # cleanest in Rewari
    ("Far Town", "Shimla", 31.10, 77.17, 40),
]


@pytest.fixture
def finder_client(client, db_engine):
    with db_engine.begin() as conn:
        did = conn.execute(text("SELECT id FROM districts WHERE slug = 'delhi'")).scalar_one()
        hour = NOW - timedelta(hours=1)
        for i, (name, city, lat, lon, aqi) in enumerate(STATIONS):
            sid = conn.execute(
                text(
                    "INSERT INTO stations (source, external_id, name, city, state, lat, lon,"
                    " district_id) VALUES ('cpcb', :e, :n, :c, 'X', :lat, :lon, :d) RETURNING id"
                ),
                {"e": f"fs{i}", "n": name, "c": city, "lat": lat, "lon": lon, "d": did},
            ).scalar_one()
            for pol, v in (("pm25", aqi), ("pm10", aqi - 10), ("no2", 30)):
                conn.execute(
                    text(
                        "INSERT INTO readings (station_id, hour, pollutant, value, unit, status,"
                        " source, fetched_at) VALUES (:s, :h, :p, :v, 'aqi_subindex', 'ok', 'cpcb',"
                        " now())"
                    ),
                    {"s": sid, "h": hour, "p": pol, "v": float(v)},
                )
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        n = len(request.url.params.get("latitude", "0").split(","))
        if request.url.host == "air-quality-api.open-meteo.com":
            times = [f"2026-11-{8 + d:02d}T{h:02d}:00" for d in range(3) for h in range(24)]
            loc = {
                "hourly": {
                    "time": times,
                    "pm2_5": [40.0] * 72,
                    "pm10": [60.0] * 72,
                    "nitrogen_dioxide": [20.0] * 72,
                    "sulphur_dioxide": [5.0] * 72,
                    "carbon_monoxide": [500.0] * 72,
                    "ozone": [40.0] * 72,
                }
            }
            return httpx.Response(200, json=[loc] * n if n > 1 else loc)
        if request.url.host == "api.open-meteo.com":
            lats = [float(x) for x in request.url.params["latitude"].split(",")]
            locs = []
            for lat in lats:
                feels = 36.0 if abs(lat - 28.61) < 0.05 else (22.0 if lat > 30 else 33.0)
                if abs(lat - 28.19) < 0.001:  # one place without data: must be skipped
                    locs.append(
                        {
                            "daily": {
                                "time": [],
                                "temperature_2m_max": [],
                                "apparent_temperature_max": [],
                                "relative_humidity_2m_mean": [],
                            }
                        }
                    )
                    continue
                locs.append(
                    {
                        "daily": {
                            "time": ["2026-11-08", "2026-11-09", "2026-11-10"],
                            "temperature_2m_max": [feels - 2] * 3,
                            "apparent_temperature_max": [feels] * 3,
                            "relative_humidity_2m_mean": [50] * 3,
                        }
                    }
                )
            return httpx.Response(200, json=locs if len(locs) > 1 else locs[0])
        if request.url.host == "router.project-osrm.org":
            return httpx.Response(
                200,
                json={
                    "code": "Ok",
                    "routes": [
                        {
                            "distance": 203400,
                            "duration": 9120,
                            "geometry": {"coordinates": [[77.209, 28.6139], [78.0, 27.2]]},
                        }
                    ],
                },
            )
        return httpx.Response(404)

    cache.clear()
    app.dependency_overrides[get_http] = lambda: httpx.Client(
        transport=httpx.MockTransport(handler)
    )
    client.calls = calls
    return client


def test_air_nearby_only_cleaner_stations_with_labels(finder_client):
    body = finder_client.get("/api/v1/finder?goal=air&mode=nearby&from=delhi").json()
    assert_meta(body, "mixed")
    names = [p["name"] for p in body["places"]]
    assert names == ["Near Clean"]  # Near Dirty is worse than here; others are > 10 km
    p = body["places"][0]
    assert p["value_label"] == "measured" and p["forecast_label"] == "estimated"
    assert len(p["forecast"]) == 3 and p["better_by"] == body["origin"]["value"] - 120
    assert body["precautions"] and "CPCB" in body["precautions"][0]["source"]


def test_air_daytrip_one_entry_per_town_beyond_10km(finder_client):
    body = finder_client.get("/api/v1/finder?goal=air&mode=daytrip&from=delhi").json()
    places = body["places"]
    assert [p["name"] for p in places] == ["Rewari"] and places[0]["value"] == 70
    assert places[0]["kind"] == "town" and places[0]["distance_km"] > 10


def test_air_vacation_reaches_all_india(finder_client):
    body = finder_client.get("/api/v1/finder?goal=air&mode=vacation&from=delhi").json()
    assert body["places"][0]["name"] == "Shimla" and body["radius_km"] is None


def test_heat_nearby_is_an_honest_empty_state(finder_client):
    body = finder_client.get("/api/v1/finder?goal=heat&mode=nearby&from=delhi").json()
    assert body["places"] == [] and "satellite" in body["empty_reason"]
    assert all("NDMA" in p["source"] for p in body["precautions"])


def test_heat_never_without_data_and_ranked_by_comfort(finder_client):
    body = finder_client.get("/api/v1/finder?goal=heat&mode=vacation&from=delhi").json()
    assert body["origin"]["value"] == 36.0
    places = body["places"]
    names = {p["name"] for p in places}
    assert places, "hill stations north of 30N are 22 degC in the mock"
    assert "Rewari" not in names  # its forecast has no data: never recommended
    assert all(p["value"] <= 35.0 and p["value_label"] == "estimated" for p in places)
    assert all(p["forecast"] for p in places)
    gaps = [p["score"] for p in places]
    assert gaps == sorted(gaps)  # comfort gap ascending
    assert places[0]["value"] == 22.0 and places[0]["score"] == 0  # inside the comfort band


def test_bad_origin(finder_client):
    assert finder_client.get("/api/v1/finder?goal=air&mode=nearby&from=atlantis").status_code == 422
    assert finder_client.get("/api/v1/finder?goal=air&mode=nearby&from=51.5,0.1").status_code == 422
    assert finder_client.get("/api/v1/finder?goal=air&mode=far&from=delhi").status_code == 422


def test_route_and_maps_link(finder_client):
    body = finder_client.get("/api/v1/route?from=28.6139,77.209&to=27.2,78.0").json()
    assert_meta(body, "estimated")
    assert body["distance_km"] == 203.4 and body["duration_min"] == 152
    assert body["geometry"][0] == [28.6139, 77.209]  # [lat, lon]
    assert "google.com/maps/dir" in body["maps_url"] and "destination=27.2,78.0" in body["maps_url"]
    assert finder_client.get("/api/v1/route?from=x&to=1,2").status_code == 422


def test_helpers():
    assert approx_minutes(60, "daytrip") == 80 and approx_minutes(1, "nearby") == 5
    assert comfort_gap(22) == 0 and comfort_gap(8) == 10 and comfort_gap(30) == 3
