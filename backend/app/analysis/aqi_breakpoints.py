"""CPCB National Air Quality Index breakpoints (single source of truth).

Source: CPCB, "National Air Quality Index" (2014), breakpoint table; lower bands
cross-checked on 2026-11-23 against IES Arthapedia "National Air Quality Index"
(https://ies.gov.in/arthapedia/concept/national-air-quality-index) and the CPCB-derived table
in PMC7397983 (https://pmc.ncbi.nlm.nih.gov/articles/PMC7397983/table/table-1).

Units: ug/m3, except CO in mg/m3.
Averaging: 24 h for PM2.5, PM10, NO2, SO2, NH3 (at least 16 valid hours);
8 h (daily maximum of running 8-h means) for CO and O3.

PROVISIONAL: CPCB lists the Severe band open-ended ("250+"). The upper concentration that maps
to 500 below continues each pollutant's Very-poor slope (e.g. PM2.5 250 -> 380, PM10 430 -> 510).
Confirm against the CPCB 2014 NAQI report before launch. Sub-indices are capped at 500.
"""

# AQI bands: (I_lo, I_hi)
AQI_BANDS = ((0, 50), (51, 100), (101, 200), (201, 300), (301, 400), (401, 500))

CATEGORIES = (
    # (upper AQI, name, key)
    (50, "Good", "good"),
    (100, "Satisfactory", "satisfactory"),
    (200, "Moderate", "moderate"),
    (300, "Poor", "poor"),
    (400, "Very poor", "verypoor"),
    (500, "Severe", "severe"),
)

# Concentration bands per pollutant: (B_lo, B_hi) for each AQI band above.
CONCENTRATION_BANDS: dict[str, tuple[tuple[float, float], ...]] = {
    "pm25": ((0, 30), (31, 60), (61, 90), (91, 120), (121, 250), (251, 380)),
    "pm10": ((0, 50), (51, 100), (101, 250), (251, 350), (351, 430), (431, 510)),
    "no2": ((0, 40), (41, 80), (81, 180), (181, 280), (281, 400), (401, 520)),
    "o3": ((0, 50), (51, 100), (101, 168), (169, 208), (209, 748), (749, 1000)),
    "co": ((0, 1.0), (1.1, 2.0), (2.1, 10), (10.1, 17), (17.1, 34), (34.1, 50)),
    "so2": ((0, 40), (41, 80), (81, 380), (381, 800), (801, 1600), (1601, 2400)),
    "nh3": ((0, 200), (201, 400), (401, 800), (801, 1200), (1201, 1800), (1801, 2400)),
}

EIGHT_HOUR = frozenset({"co", "o3"})
MIN_HOURS_24H = 16  # CPCB: at least 16 hours of data for a 24-hour average
MIN_HOURS_8H = 6  # our choice for a running 8-hour mean (75% of hours)
MIN_POLLUTANTS = 3  # CPCB: AQI needs at least 3 pollutants ...
REQUIRED_ONE_OF = frozenset({"pm25", "pm10"})  # ... one of which is PM2.5 or PM10
