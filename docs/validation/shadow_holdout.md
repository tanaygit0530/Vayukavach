# Shadow AQI estimates: hold-out test

Generated 2026-11-24 06:46 UTC by `backend/scripts/validate_shadow.py` on stored CPCB/SPCB station data (OpenAQ), 2026-10-25 to 2026-11-23 (30 days).

Each day, 10% of the real hourly readings per city and pollutant were hidden and estimated from stations within 15 km in the same hour (the shadow AQI method). Baseline: the mean of all other stations in the city that hour. Only cells both methods could estimate are scored. Errors are in µg/m³.

## PM2.5

| City | Hidden readings | Mean level | Shadow error (MAE) | Relative | Baseline MAE |
|---|--:|--:|--:|--:|--:|
| Delhi | 3,053 | 156 | **46.7** | 30% | 47.2 |
| Mumbai | 1,858 | 55 | **16.9** | 31% | 16.2 |
| Kolkata | 688 | 49 | **13.3** | 27% | 12.4 |
| Hyderabad | 591 | 33 | **13.2** | 39% | 11.8 |
| Bengaluru | 443 | 43 | **17.8** | 42% | 16.4 |
| Patna | 433 | 67 | **31.7** | 48% | 28.5 |
| Chennai | 419 | 55 | **16.0** | 29% | 14.1 |
| Lucknow | 368 | 77 | **31.4** | 41% | 30.6 |
| Kanpur | 181 | 70 | **26.4** | 38% | 22.8 |
| **All cities** | **8,034** | 93 | **29.3** | 32% | 28.7 |

Single hidden readings: shadow estimates are about as accurate as the city-mean baseline (-2%).

## PM10

| City | Hidden readings | Mean level | Shadow error (MAE) | Relative | Baseline MAE |
|---|--:|--:|--:|--:|--:|
| Delhi | 2,963 | 262 | **69.5** | 27% | 69.5 |
| Mumbai | 1,722 | 114 | **33.7** | 29% | 31.2 |
| Kolkata | 683 | 95 | **25.8** | 27% | 25.4 |
| Hyderabad | 528 | 74 | **28.4** | 38% | 23.2 |
| Bengaluru | 461 | 101 | **32.1** | 32% | 32.3 |
| Chennai | 388 | 115 | **45.4** | 39% | 37.5 |
| Patna | 372 | 128 | **52.4** | 41% | 49.7 |
| Lucknow | 369 | 133 | **49.9** | 38% | 50.0 |
| Kanpur | 185 | 134 | **43.1** | 32% | 41.1 |
| **All cities** | **7,671** | 168 | **48.9** | 29% | 47.4 |

Single hidden readings: shadow estimates are about as accurate as the city-mean baseline (-3%).

## City PM2.5 index for the day (what the app shows)

City PM2.5 sub-index (India AQI scale) from all real readings = truth. Then readings are hidden and the index is recomputed two ways: **without** the hidden hours (what an official average does) and with them **filled by the shadow method**.

- *Random gaps*: 10% of readings hidden at random.
- *Peak gaps* (Diwali-style): in the 6 most polluted hours, the most polluted third of the stations go silent.

| Gaps | City-days | Error without the gaps (AQI points) | Bias | Shadow error | Bias | Ratio-scaled prototype | Bias |
|---|--:|--:|--:|--:|--:|--:|--:|
| Random | 250 | 1.1 | -0.3 | **3.6** | +0.8 | 2.2 | +0.6 |
| Peak (Diwali-style) | 250 | 10.7 | -10.7 | **9.8** | -9.5 | 7.1 | -6.8 |

With Diwali-style gaps, leaving the gaps out reads **10.7 points too clean** on average; the shadow index cuts that error by 8%. The ratio-scaled prototype (each station's usual ratio to the rest of the city that day, times the city in the missing hour) cuts it by 33%; it is not in the app yet.

With random gaps, leaving them out is already accurate (daily means barely move), and filling adds estimation noise. The shadow index is useful when gaps cluster in polluted hours, which the app flags as *missing when it mattered*.

| City | City-days | Without the gaps | Shadow |
|---|--:|--:|--:|
| Bengaluru | 28 | 6.2 | **8.8** |
| Chennai | 28 | 7.4 | **6.5** |
| Delhi | 28 | 11.5 | **9.0** |
| Hyderabad | 28 | 3.5 | **4.7** |
| Kanpur | 26 | 18.0 | **11.5** |
| Kolkata | 28 | 7.6 | **6.2** |
| Lucknow | 28 | 13.8 | **12.3** |
| Mumbai | 28 | 11.1 | **11.9** |
| Patna | 28 | 17.2 | **17.9** |
