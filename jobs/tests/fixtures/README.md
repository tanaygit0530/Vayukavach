# Test fixtures

| File | Origin |
| --- | --- |
| `cpcb_delhi.json` | Recorded 2026-11-23 from data.gov.in resource 3b01bcb8… (`filters[city]=Delhi`, two pages of 10 merged; duplicates across pages kept on purpose) |
| `openmeteo_air_delhi_kanpur.json` | Recorded 2026-11-23 from the Open-Meteo Air Quality API (Delhi, Kanpur) |
| `openmeteo_wx_delhi_kanpur.json` | Recorded 2026-11-23 from the Open-Meteo Forecast API (Delhi, Kanpur) |
| `openaq_recorded_*.json` | Recorded 2026-11-23 from OpenAQ v3: locations in a box around Delhi, sensors of location 17 (R K Puram, includes retired 2016-18 sensors), PM2.5 and NO₂ (ppb) hours |
| `openaq_locations_delhi.json`, `openaq_location_8118_sensors.json`, `openaq_hours_*.json` | Small constructed fixtures in the recorded shape, with a gap, a negative value, a >999 value and a retired sensor. Times fixed around 2026-11-23 12:45 UTC |
