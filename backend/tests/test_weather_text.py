from app.services.weather import feels_like_reason


def test_sun_only_mentioned_when_uv_is_up():
    assert "sun" in feels_like_reason(30, 32, 40, 3, uv=7).lower()
    night = feels_like_reason(30, 32, 40, 3, uv=0)
    assert "sun" not in night.lower() and "warmer" in night


def test_other_reasons():
    assert "Humid" in feels_like_reason(30, 33, 75, 3, uv=0)
    assert "Wind" in feels_like_reason(20, 17, 40, 20)
    assert "same" in feels_like_reason(20, 20.4, 40, 3)
    assert feels_like_reason(None, 20, 40, 3) is None
