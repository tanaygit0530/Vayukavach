from tests.api.conftest import assert_meta


def test_air_now_official_with_completeness_and_shadow(client):
    body = client.get("/api/v1/air/delhi/now").json()
    assert_meta(body, "measured")
    assert body["aqi_kind"] == "official" and body["aqi"] == 310  # CPCB 4 PM bulletin value
    assert body["category"] == "Very poor"
    assert body["completeness_pct"] is not None
    assert body["shadow_aqi"] is not None and body["shadow_label"] == "estimated"
    assert body["visibility_m"] == 3500
    assert body["stale"] is True  # bulletin hour (16:00) is 4.5 h before 20:30


def test_air_now_model_only_district_is_estimated(client):
    body = client.get("/api/v1/air/shimla/now").json()
    assert_meta(body, "estimated")
    assert body["aqi_kind"] == "cams" and body["aqi"] is not None
    assert body["shadow_aqi"] is None and body["completeness_pct"] is None
    assert body["stale"] is False


def test_unknown_district_404(client):
    assert client.get("/api/v1/air/atlantis/now").status_code == 404


def test_air_hourly_has_24_hours_with_forecast_split(client):
    body = client.get("/api/v1/air/delhi/hourly").json()
    assert_meta(body, "mixed")
    hours = body["hours"]
    assert len(hours) == 24
    assert hours[16]["official_aqi"] == 310
    assert hours[21]["is_forecast"] and not hours[19]["is_forecast"]
    assert all(h["hour"].endswith("+05:30") for h in hours)
    assert any(h["official_missing"] for h in hours if not h["is_forecast"])


def test_air_daily_ten_days_with_outlook_placeholders(client):
    body = client.get("/api/v1/air/shimla/daily").json()
    assert_meta(body, "estimated")
    days = body["days"]
    assert len(days) == 10
    assert all(d["is_outlook"] and not d["available"] and d["low"] is None for d in days[5:])
    assert days[1]["available"] and days[1]["low"] <= days[1]["high"]


def test_air_monthly_twelve_months_no_zeros(client):
    body = client.get("/api/v1/air/delhi/monthly").json()
    months = body["months"]
    assert len(months) == 12 and months[-1]["is_current"]
    assert months[-1]["avg_aqi"] is not None
    assert all(m["avg_aqi"] is None for m in months if m["days"] == 0)


def test_air_pollutants_stations_then_model(client):
    delhi = client.get("/api/v1/air/delhi/pollutants").json()
    assert_meta(delhi)
    pm25 = next(p for p in delhi["pollutants"] if p["pollutant"] == "pm25")
    assert pm25["label"] == "measured" and pm25["stations"] > 0 and pm25["sub_index"] > 0
    shimla = client.get("/api/v1/air/shimla/pollutants").json()
    pm25 = next(p for p in shimla["pollutants"] if p["pollutant"] == "pm25")
    assert pm25["label"] == "estimated" and pm25["value"] == 40.0
    assert shimla["co2"]["unit"] == "ppm" and "not part" in shimla["co2"]["note"]
    so2 = next(p for p in shimla["pollutants"] if p["pollutant"] == "so2")
    assert so2["value"] is None  # no data -> null, never 0


def test_air_stations_pins(client):
    body = client.get("/api/v1/air/delhi/stations").json()
    assert_meta(body)
    assert len(body["stations"]) == 1
    pin = body["stations"][0]
    assert pin["status"] == "measured" and pin["aqi"] == 310 and pin["category_key"] == "verypoor"


def test_wind_and_advice(client):
    wind = client.get("/api/v1/air/delhi/wind").json()
    assert_meta(wind, "estimated")
    assert wind["direction_compass"] == "WNW" and "trapping" in wind["note"]
    advice = client.get("/api/v1/air/delhi/advice").json()
    assert advice["category_key"] == "verypoor"
    assert "respiratory illness" in advice["health_impact"]
    assert "CPCB" in advice["advice_source"]


def test_air_map_grid_and_validation(client):
    body = client.get("/api/v1/air/map", params={"bbox": "76.8,28.4,77.4,28.9"}).json()
    assert_meta(body, "estimated")
    assert len(body["cells"]) == 25 and body["cells"][0]["pm25_sub_index"] is not None
    assert client.get("/api/v1/air/map", params={"bbox": "1,2,3"}).status_code == 422
    assert client.get("/api/v1/air/map", params={"bbox": "60,5,90,35"}).status_code == 422


def test_air_daily_serves_stored_forecasts(client, db_engine):
    from datetime import timedelta

    from sqlalchemy import text

    from app.analysis.time import ist_date
    from tests.api.conftest import NOW

    today = ist_date(NOW)
    with db_engine.begin() as conn:
        did = conn.execute(text("SELECT id FROM districts WHERE slug = 'delhi'")).scalar_one()
        for i in range(10):
            method = "cams_corrected" if i < 5 else "outlook"
            conn.execute(
                text(
                    "INSERT INTO aqi_forecast_daily (district_id, issue_date, target_date,"
                    " lead_days, low, median, high, method, model_version, created_at) VALUES"
                    " (:d, :issue, :t, :lead, :lo, :mid, :hi, :m, 'v-test', now())"
                ),
                {"d": did, "issue": today, "t": today + timedelta(days=i), "lead": i + 1,
                 "lo": 200 + i, "mid": 240 + i, "hi": 280 + i, "m": method},
            )  # fmt: skip
    body = client.get("/api/v1/air/delhi/daily").json()
    days = body["days"]
    assert len(days) == 10 and all(d["available"] for d in days)
    assert days[0]["method"] == "cams_corrected" and days[0]["median"] == 240
    assert days[7]["is_outlook"] and days[7]["method"] == "outlook" and days[7]["low"] == 207
    assert "bias-corrected" in body["note"] and "outlook model" in body["note"]
