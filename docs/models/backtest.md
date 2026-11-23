# AQI forecast backtest

Rolling backtest: 48 weekly issue dates from 2025-11-20 to 2026-11-12; models are
retrained before every issue date on data available then. Target: daily city AQI
(India AQI, sub-index of daily mean concentrations, mean over stations).
Day 1 = issue date (today), day L = issue + L - 1.

## MAE (AQI points) per day ahead

| Day | Corrected CAMS | Raw CAMS | Outlook (median) | Tomorrow = today | Month average |
| --- | --- | --- | --- | --- | --- |
| 1 | **17.2** | 50.6 | – | 18.2 | – |
| 2 | **18.9** | 52.8 | – | 24.5 | – |
| 3 | **19.0** | 53.8 | – | 26.3 | – |
| 4 | **21.7** | 53.2 | – | 28.2 | – |
| 5 | **19.8** | 55.1 | – | 26.3 | – |
| 6 | – | – | **19.1** | 25.7 | 22.8 |
| 7 | – | – | **21.2** | 26.2 | 23.2 |
| 8 | – | – | **22.2** | 28.1 | 25.0 |
| 9 | – | – | **21.5** | 29.4 | 26.2 |
| 10 | – | – | **21.5** | 30.0 | 25.9 |

## Category hit rate (same CPCB category as the truth)

| Day | Corrected CAMS | Raw CAMS | Outlook (median) | Tomorrow = today | Month average |
| --- | --- | --- | --- | --- | --- |
| 1 | 74% | 44% | – | 75% | – |
| 2 | 72% | 45% | – | 64% | – |
| 3 | 70% | 45% | – | 63% | – |
| 4 | 69% | 40% | – | 58% | – |
| 5 | 74% | 47% | – | 61% | – |
| 6 | – | – | 69% | 61% | 63% |
| 7 | – | – | 66% | 56% | 63% |
| 8 | – | – | 69% | 57% | 61% |
| 9 | – | – | 66% | 54% | 59% |
| 10 | – | – | 69% | 57% | 64% |

## Verdict

- Days 1–5: corrected CAMS MAE 19.3 vs raw CAMS 53.1 and tomorrow = today 24.7 → **beats both baselines**.
- Days 6–10: outlook MAE 21.1 vs tomorrow = today 27.9 and month average 24.6 → **beats both baselines**.
- Outlook range (5–95% quantile models) contains the truth 75% of the time (target: at least 80%).

## Limits (read before trusting these numbers)

- The CAMS archive holds analyses, not past forecasts: days 1–5 use CAMS at lead 0 for
  every day, so their skill here is an upper bound; real forecasts will do worse.
- The outlook uses observed (reanalysis) weather for target days; live serving uses the
  weather forecast, so real skill is lower.
- Raw CAMS has no free forecast beyond day 5, so days 6–10 compare against tomorrow =
  today and the city's month average instead.
- Truth is computed from OpenAQ daily means of CPCB/SPCB monitors (sub-index of daily
  means); it tracks CPCB's published AQI but is not identical to it.
