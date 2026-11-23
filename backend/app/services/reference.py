"""Fixed reference text and lookups (official wording where it exists)."""

# CPCB National AQI: "associated health impacts" per category (CPCB, NAQI 2014).
CPCB_HEALTH = {
    "good": "Minimal impact.",
    "satisfactory": "May cause minor breathing discomfort to sensitive people.",
    "moderate": "May cause breathing discomfort to people with lung disease such as asthma, "
    "and discomfort to people with heart disease, children and older adults.",
    "poor": "May cause breathing discomfort to people on prolonged exposure, and discomfort "
    "to people with heart disease.",
    "verypoor": "May cause respiratory illness to people on prolonged exposure. Effect may be "
    "more pronounced in people with lung and heart diseases.",
    "severe": "May cause respiratory impact even on healthy people, and serious health impacts "
    "on people with lung or heart disease. Effects may be felt even during light physical "
    "activity.",
}
CPCB_HEALTH_SOURCE = "CPCB, National Air Quality Index (2014): associated health impacts"

# WMO weather interpretation codes used by Open-Meteo.
WMO = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Freezing fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    56: "Light freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Heavy showers",
    85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}  # fmt: skip


def condition(code: int | None) -> str | None:
    return None if code is None else WMO.get(int(code), "Unknown")


def uv_category(uv: float | None) -> str | None:
    """WHO UV index categories."""
    if uv is None:
        return None
    if uv < 3:
        return "Low"
    if uv < 6:
        return "Moderate"
    if uv < 8:
        return "High"
    if uv < 11:
        return "Very high"
    return "Extreme"


COMPASS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")  # fmt: skip


def compass(degrees: float | None) -> str | None:
    if degrees is None:
        return None
    return COMPASS[int((degrees % 360) / 22.5 + 0.5) % 16]


def dispersion_note(wind_kmh: float | None, boundary_layer_m: float | None) -> str | None:
    """Plain-language note on whether the air is clearing or trapping pollution."""
    if wind_kmh is None:
        return None
    shallow = boundary_layer_m is not None and boundary_layer_m < 300
    if wind_kmh < 5 and shallow:
        return "Calm air and a low mixing layer are trapping pollution near the ground."
    if wind_kmh < 5:
        return "Calm wind: pollution is building up rather than clearing."
    if wind_kmh < 12:
        return "Light wind: pollution is clearing slowly."
    return "Steady wind is helping to clear pollution."
