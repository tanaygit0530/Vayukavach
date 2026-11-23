# India AQI vs CPCB published sub-indices

Generated 2026-11-23 12:12 UTC. Our sub-index: CPCB breakpoints on OpenAQ hourly concentrations (24 h mean, >= 16 h; CO/O3 max 8 h mean).
CPCB: `avg_value` sub-index from the data.gov.in real-time feed, same station and hour.

## Per pollutant (difference = ours - CPCB, AQI points)

| Pollutant | n | MAE | Bias | Within ±5 | Within ±10 |
| --- | --- | --- | --- | --- | --- |
| co | 29.0 | 49.8 | -49.8 | 0% | 3% |
| no2 | 29.0 | 52.2 | 52.2 | 3% | 3% |
| o3 | 28.0 | 4.6 | 3.6 | 68% | 96% |
| pm10 | 28.0 | 4.1 | 4.0 | 71% | 100% |
| pm25 | 28.0 | 28.4 | 27.7 | 7% | 18% |
| so2 | 23.0 | 25.6 | 25.6 | 0% | 9% |

## Station AQI (highest sub-index, station-hours with ≥ 3 pollutants)

28 station-hours: MAE 31.0 points, bias +30.4, within ±5: 11%, within ±10: 14%.

| Station | Hour (IST) | CPCB AQI | Our AQI | Diff |
| --- | --- | --- | --- | --- |
| Alipur, Delhi - DPCC | 23 Nov 16:00 | 253 | 304 | +51 |
| Burari Crossing, Delhi - IITM | 23 Nov 16:00 | 306 | 337 | +31 |
| CRRI Mathura Road, Delhi - IITM | 23 Nov 16:00 | 326 | 339 | +13 |
| DTU, Delhi - CPCB | 23 Nov 16:00 | 212 | 309 | +97 |
| Dr. Karni Singh Shooting Range, Delhi - DPCC | 23 Nov 16:00 | 246 | 293 | +47 |
| Dwarka-Sector 8, Delhi - DPCC | 23 Nov 16:00 | 252 | 297 | +45 |
| IGI Airport (T3), Delhi - IITM | 23 Nov 16:00 | 214 | 215 | +1 |
| IHBAS, Dilshad Garden, Delhi - CPCB | 23 Nov 16:00 | 211 | 202 | -9 |
| IMD Lodhi Road, Delhi - IITM | 23 Nov 16:00 | 175 | 179 | +4 |
| ITO, Delhi - CPCB | 23 Nov 16:00 | 325 | 346 | +21 |
| Indirapuram, Ghaziabad - UPPCB | 23 Nov 16:00 | 213 | 230 | +17 |
| Jahangirpuri, Delhi - DPCC | 23 Nov 16:00 | 278 | 316 | +38 |
| Jawaharlal Nehru Stadium, Delhi - DPCC | 23 Nov 16:00 | 251 | 295 | +44 |
| Knowledge Park - V, Greater Noida - UPPCB | 23 Nov 16:00 | 253 | 271 | +18 |
| Loni, Ghaziabad - UPPCB | 23 Nov 16:00 | 190 | 222 | +32 |
| Major Dhyan Chand National Stadium, Delhi - DPCC | 23 Nov 16:00 | 220 | 260 | +40 |
| NSIT Dwarka, Delhi - CPCB | 23 Nov 16:00 | 201 | 202 | +1 |
| Okhla Phase-2, Delhi - DPCC | 23 Nov 16:00 | 232 | 267 | +35 |
| Patparganj, Delhi - DPCC | 23 Nov 16:00 | 227 | 268 | +41 |
| Pusa, Delhi - DPCC | 23 Nov 16:00 | 197 | 211 | +14 |
| Sector-1, Noida - UPPCB | 23 Nov 16:00 | 175 | 274 | +99 |
| Sector-116, Noida - UPPCB | 23 Nov 16:00 | 197 | 217 | +20 |
| Sector-125, Noida - UPPCB | 23 Nov 16:00 | 204 | 216 | +12 |
| Sector-62, Noida - IITM | 23 Nov 16:00 | 321 | 348 | +27 |
| Shadipur, Delhi - CPCB | 23 Nov 16:00 | 281 | 308 | +27 |
