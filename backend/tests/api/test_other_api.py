from tests.api.conftest import NOW, assert_meta


def test_places_search_marks_covered_districts(client):
    body = client.get("/api/v1/places/search", params={"q": "delhi"}).json()
    assert_meta(body)
    names = {r["name"]: r for r in body["results"]}
    assert names["New Delhi"]["covered_district"] == "delhi"
    assert names["Leh"]["covered_district"] is None
    assert client.get("/api/v1/places/search", params={"q": "x"}).status_code == 422


def test_districts_list(client):
    body = client.get("/api/v1/places/districts").json()
    assert_meta(body)
    assert {d["id"] for d in body["districts"]} == {"delhi", "shimla"}


def test_places_summary(client):
    body = client.get("/api/v1/places/summary", params={"ids": "delhi,shimla,nowhere"}).json()
    assert_meta(body, "mixed")
    by_id = {p["id"]: p for p in body["places"]}
    assert set(by_id) == {"delhi", "shimla"}
    assert by_id["delhi"]["aqi_label"] == "measured"
    assert by_id["shimla"]["aqi_label"] == "estimated"
    assert by_id["delhi"]["today_high"] == 34.0


def test_weather_now_and_hourly(client):
    now = client.get("/api/v1/weather/delhi/now").json()
    assert_meta(now, "estimated")
    assert now["condition"] == "Clear sky" and now["feels_like_reason"]
    assert now["today_low"] == 18.0 and now["stale"] is False
    hourly = client.get("/api/v1/weather/delhi/hourly").json()
    assert len(hourly["hours"]) == 48
    assert hourly["hours"][0]["hour"].endswith("+05:30")


def test_weather_daily_sun_uv(client):
    daily = client.get("/api/v1/weather/delhi/daily").json()
    assert len(daily["days"]) == 10 and daily["days"][0]["is_forecast"] is False
    assert len(client.get("/api/v1/weather/delhi/daily?days=3").json()["days"]) == 3
    assert client.get("/api/v1/weather/delhi/daily?days=40").status_code == 422
    sun = client.get("/api/v1/weather/delhi/sun").json()
    assert sun["days"][0]["sunrise"].startswith(f"{NOW.date()}T06:40") or sun["days"][0][
        "sunrise"
    ].endswith("+05:30")
    uv = client.get("/api/v1/weather/delhi/uv").json()
    assert_meta(uv, "estimated")
    assert uv["category"] == "Low"  # 20:30
    assert uv["max_category"] == "High" and uv["cover_up_from"] is not None


def test_heat(client):
    body = client.get("/api/v1/heat/delhi").json()
    assert_meta(body, "estimated")
    assert body["level"] in {"normal", "caution", "danger", "extreme"}
    assert body["heat_index"] is not None and body["wet_bulb"] is not None
    assert len(body["hourly"]) == 24
    assert body["safe_work_windows"]
    assert body["tips"] and "NDMA" in body["tips_source"]
    assert "draft" in body["thresholds_status"]
    assert len(body["daily"]) >= 2


def test_gap_report_json_and_csv(client, db_engine):
    from datetime import timedelta

    from sqlalchemy.orm import Session

    from app.analysis.summary import build_city_day
    from app.analysis.time import day_bounds
    from app.api.common import get_now
    from app.main import app
    from app.models import District
    from tests.analysis.helpers import DAY

    later = day_bounds(DAY)[1] + timedelta(hours=3)  # the day is over and settled
    with Session(db_engine) as session:
        delhi = session.query(District).filter_by(slug="delhi").one()
        build_city_day(session, delhi, DAY, later)
        session.commit()
    app.dependency_overrides[get_now] = lambda: later
    body = client.get("/api/v1/reports/delhi/gaps", params={"date": str(DAY)}).json()
    assert_meta(body, "measured")
    assert body["gap_bias"]["flagged"] is True
    assert len({s["station_id"] for s in body["silent_stations"]}) == 2
    assert body["readings_near_limit"][0]["at_or_over_999"] is True
    assert "does not assign blame" in body["wording"]
    csv = client.get("/api/v1/reports/delhi/gaps", params={"format": "csv", "date": str(DAY)})
    assert csv.headers["content-type"].startswith("text/csv")
    lines = csv.text.strip().splitlines()
    assert lines[0].startswith("station_id,station,pollutant") and len(lines) == 1 + 12


def test_openapi_lists_every_endpoint(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert len([p for p in paths if p.startswith("/api/v1")]) == 20


def test_rate_limit_returns_429():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.ratelimit import RateLimitMiddleware

    mini = FastAPI()
    mini.add_middleware(RateLimitMiddleware, per_minute=3)
    mini.get("/x")(lambda: {"ok": True})
    c = TestClient(mini)
    codes = [c.get("/x").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[-1] == 429


def test_safe_work_windows_match_the_hourly_levels(client):
    body = client.get("/api/v1/heat/delhi").json()
    normal = {h["local_hour"] for h in body["hourly"] if h["level"] == "normal"}
    expected, start = [], None
    for clock in range(6, 19):  # work day 6 AM to 7 PM
        if clock in normal and start is None:
            start = clock
        if clock not in normal and start is not None:
            expected.append({"from_hour": start, "to_hour": clock})
            start = None
    if start is not None:
        expected.append({"from_hour": start, "to_hour": 19})
    assert body["safe_work_windows"] == expected
    levels = {h["level"] for h in body["hourly"]}
    assert levels <= {"normal", "caution", "danger", "extreme"}


def test_heat_levels_follow_the_hottest_hours(client):
    body = client.get("/api/v1/heat/delhi").json()
    hottest = max(body["hourly"], key=lambda h: h["heat_index"])
    order = ["normal", "caution", "danger", "extreme"]
    assert order.index(body["worst_level_today"]) >= order.index(hottest["level"])
