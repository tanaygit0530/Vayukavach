# India AQI vs CPCB published sub-indices

Generated 2026-11-23 12:22 UTC. Our sub-index: CPCB breakpoints on OpenAQ hourly concentrations of the same station. 24-h pollutants: mean of the hourly sub-indices (>= 16 h); CO/O3: sub-index of the 8-h running mean.
CPCB: `avg_value` sub-index from the data.gov.in real-time feed, same station and hour (`last_update` = end of the hour).

## Per pollutant (difference = ours - CPCB, AQI points)

| Pollutant | n | MAE | Bias | Within ±5 | Within ±10 |
| --- | --- | --- | --- | --- | --- |
| co | 39.0 | 5.3 | -1.1 | 85% | 90% |
| no2 | 40.0 | 1.7 | -0.1 | 98% | 98% |
| o3 | 38.0 | 1.1 | -0.8 | 97% | 100% |
| pm10 | 40.0 | 3.6 | 2.9 | 90% | 92% |
| pm25 | 40.0 | 7.2 | 6.8 | 40% | 92% |
| so2 | 34.0 | 0.2 | -0.1 | 100% | 100% |

## Station AQI (highest sub-index, station-hours with ≥ 3 pollutants)

40 station-hours: MAE 7.4 points, bias +6.9, within ±5: 35%, within ±10: 90%.

| Station | Hour (IST) | CPCB AQI | Our AQI | Diff |
| --- | --- | --- | --- | --- |
| Alipur, Delhi - DPCC | 23 Nov 15:00 | 253 | 262 | +9 |
| Ashok Vihar, Delhi - DPCC | 23 Nov 15:00 | 244 | 252 | +8 |
| Bawana, Delhi - DPCC | 23 Nov 15:00 | 283 | 293 | +10 |
| Burari Crossing, Delhi - IITM | 23 Nov 15:00 | 306 | 312 | +6 |
| CRRI Mathura Road, Delhi - IITM | 23 Nov 15:00 | 326 | 330 | +4 |
| Chandni Chowk, Delhi - IITM | 23 Nov 15:00 | 278 | 284 | +6 |
| DTU, Delhi - CPCB | 23 Nov 15:00 | 212 | 225 | +13 |
| Dr. Karni Singh Shooting Range, Delhi - DPCC | 23 Nov 15:00 | 246 | 251 | +5 |
| Dwarka-Sector 8, Delhi - DPCC | 23 Nov 15:00 | 252 | 259 | +7 |
| IGI Airport (T3), Delhi - IITM | 23 Nov 15:00 | 214 | 218 | +4 |
| IHBAS, Dilshad Garden, Delhi - CPCB | 23 Nov 15:00 | 211 | 204 | -7 |
| IMD Lodhi Road, Delhi - IITM | 23 Nov 15:00 | 175 | 177 | +2 |
| Indirapuram, Ghaziabad - UPPCB | 23 Nov 15:00 | 213 | 215 | +2 |
| Jahangirpuri, Delhi - DPCC | 23 Nov 15:00 | 278 | 284 | +6 |
| Jawaharlal Nehru Stadium, Delhi - DPCC | 23 Nov 15:00 | 251 | 253 | +2 |
| Knowledge Park - V, Greater Noida - UPPCB | 23 Nov 15:00 | 253 | 260 | +7 |
| Lodhi Road, Delhi - IITM | 23 Nov 15:00 | 157 | 155 | -2 |
| Loni, Ghaziabad - UPPCB | 23 Nov 15:00 | 190 | 197 | +7 |
| Major Dhyan Chand National Stadium, Delhi - DPCC | 23 Nov 15:00 | 220 | 227 | +7 |
| Mundka, Delhi - DPCC | 23 Nov 15:00 | 283 | 292 | +9 |
| NSIT Dwarka, Delhi - CPCB | 23 Nov 15:00 | 201 | 202 | +1 |
| Nangloi, Delhi-DPCC | 23 Nov 15:00 | 229 | 292 | +63 |
| Nehru Nagar, Delhi - DPCC | 23 Nov 15:00 | 279 | 290 | +11 |
| Okhla Phase-2, Delhi - DPCC | 23 Nov 15:00 | 232 | 236 | +4 |
| Patparganj, Delhi - DPCC | 23 Nov 15:00 | 227 | 233 | +6 |

## Averaging method check (all pollutants pooled per method)

| Method | n | MAE | Bias |
| --- | --- | --- | --- |
| cpcb_feed (pm25) | 40 | 7.2 | +6.8 |
| cpcb_feed (pm10) | 40 | 3.6 | +2.9 |
| concentration_mean (pm25) | 40 | 26.7 | +25.7 |
| concentration_mean (pm10) | 40 | 4.4 | +2.0 |
