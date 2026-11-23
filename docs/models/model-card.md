# Model card: VayuKavach AQI forecasts

| | Days 1–5: corrected CAMS | Days 6–10: outlook |
|---|---|---|
| **What** | LightGBM, one model per pollutant (PM2.5, PM10, NO₂, SO₂, CO, O₃), pooled over cities with the city as a feature | LightGBM quantile regression (5%, 50%, 95%) on daily city AQI |
| **Inputs** | CAMS daily mean for the target day, station value observed the day before the issue date and its 3-day mean, day ahead, month, Diwali window, stubble season, weather (temperature, humidity, wind, rain, mixing-layer height) | Last 7 days of daily AQI, day ahead, day of week, month, Diwali window, stubble season, weather for the target day |
| **Output** | Corrected daily pollutant values → India AQI (Phase 2 code). The day's range comes from the hourly CAMS shape, centred on that value | Median + 5–95% range |
| **Target** | Daily city AQI from OpenAQ daily means of CPCB/SPCB monitors (sub-index of the daily mean, ≥ 16 h, ≥ 3 pollutants incl. PM, mean over stations) | same |
| **Training data** | Jan 2025 → yesterday, 9 cities (5,597 city-days); Shimla has no station and stays on raw CAMS | same |
| **Retrained** | Nightly (GitHub Actions, 03:07 IST), after a 52-week rolling backtest | same |
| **Served only if** | It beats raw CAMS **and** tomorrow = today in the backtest; otherwise raw CAMS is served | It beats tomorrow = today **and** the month average; otherwise days 6–10 are hidden |

## Results (52-week rolling backtest, 2026-11-23)

| | Ours | Raw CAMS | Tomorrow = today | Month average |
|---|---|---|---|---|
| Days 1–5, MAE (AQI points) | **19.3** | 53.1 | 24.7 | – |
| Days 6–10, MAE | **21.1** | – | 27.9 | 24.6 |
| Days 1–5, same CPCB category | **70–74%** | 40–47% | 58–75% | – |
| Outlook range coverage | 75% (target ≥ 80%) | | | |

Per-day tables: [backtest.md](backtest.md). Notebook: [aqi_forecast.ipynb](aqi_forecast.ipynb).

## What changed the result

The first correction model (PM only, no observations) beat raw CAMS but lost to
tomorrow = today (29.7 vs 24.7). Two fixes:
1. Add the station value observed the day before the issue date: standard model-output
   statistics.
2. Correct **all six pollutants**: raw CAMS ozone runs high in India and set the "corrected"
   AQI in 35 of 45 diagnostic cases, hiding the PM correction.

## Limits

- The CAMS archive holds analyses, not past forecasts: the days 1–5 backtest is an upper bound.
- The outlook backtest uses observed weather for target days; live serving uses forecasts.
- Outlook ranges are a little too narrow (75% vs 80% coverage); calibration is future work.
- The target tracks CPCB's published AQI but is computed from OpenAQ daily means, not CPCB's
  own bulletins.
