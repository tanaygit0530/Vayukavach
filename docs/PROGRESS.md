# VayuKavach progress

## Phase 0: Project setup — complete (2026-11-23)

**Built**
- Monorepo: `backend/` (FastAPI, `/health`, SQLAlchemy base, Alembic, pytest, ruff), `jobs/` (uv project,
  `run.py` job entry point, tests), `frontend/` (React 19 + Vite + TypeScript 5.9 + Tailwind 3, ESLint,
  blank home page with Outfit font and starter design tokens).
- `.env.example` (DATABASE_URL, DATA_GOV_IN_API_KEY, OPENAQ_API_KEY, GEMINI_API_KEY, TELEGRAM_BOT_TOKEN,
  FRONTEND_ORIGIN), `docker-compose.yml` (Postgres 16), CI workflow `.github/workflows/ci.yml`.
- `CLAUDE.md`, `docs/README.md` (architecture + setup), this file.

**Checks**
| Done when | Result |
| --- | --- |
| `docker compose up` starts Postgres | Pass (container healthy, Alembic connects) |
| Backend `/health` returns OK | Pass (`{"status":"ok","database":"ok"}`) |
| Frontend loads | Pass (http://localhost:5180) |
| CI passes | Pass (GitHub Actions run 45164431436, all three jobs green) |

Tests: backend 1 passed, jobs 2 passed; ruff, ESLint and `vite build` clean.

**Known issues / decisions**
- Ports: Docker Postgres on host **5433** (local Postgres 14 owns 5432); Vite on **5180** (another project's
  container owns 5173).
- TypeScript pinned to 5.9: typescript-eslint does not support TypeScript 7 yet.
- Starlette prints a deprecation warning about httpx in `TestClient`; harmless.
- `docs/mockups/` and reference images ref-01 / ref-03 are not in the repo yet.
- The build prompts file is named `VayuKavach Phase-wise Build Prompts.md`, not `BUILD_PROMPTS.md`.


## Phase 1: Hourly data pipeline — complete except the spaced-run check (2026-11-23)

Update after the API keys arrived: CPCB live pull stored 3,978 station-pollutant rows (570
stations, all India; 9 of the 10 cities). **Shimla has no live CPCB station** (nearest:
Baddi, ~35 km, not counted). OpenAQ backfill: 48+ Delhi monitors with 90 days of hours;
other cities continue over the next hourly runs (1,500 requests per run). OpenAQ fixes:
retired sensors skipped via a `sensors` table (refreshed daily), monitors first,
`stations.is_reference`, a broken location or sensor no longer fails the run.
Three runs spaced one hour apart are scheduled for 18:10, 19:10 and 20:10 IST.

### Original Phase 1 notes

**Built**
- Alembic migration `0001`: `districts`, `stations`, `readings`, `model_air`, `weather`,
  `weather_daily`, `fetch_log`. Check constraints enforce that missing = NULL value
  (`status='missing'` plus `reason`), and real values are never NULL.
- Collectors in `jobs/collectors/` with retries plus exponential backoff (timeouts, 429, 5xx):
  - `cpcb`: data.gov.in snapshot, large pages, de-duplicated. Writes `missing` rows at the
    snapshot hour for every active station and pollutant that did not arrive. A missing marker
    never overwrites a real value; a late real value replaces a marker.
  - `openaq`: stations within 25 km of each district. 90-day backfill, then incremental,
    resuming after the last real value. Gaps inside the window are stored as `missing`.
    55 requests/min plus a 1,500-request budget per run. Units normalised (ppm/ppb to µg/m³,
    CO to mg/m³); PM ≥ 999 µg/m³ marked `excluded_over_999`.
  - `openmeteo-air` (CAMS, 5-day forecast) and `weather` (hourly plus daily, 16-day,
    past_days=1, timezone=Asia/Kolkata).
- `run.py hourly` runs each collector independently and logs each in `fetch_log`
  (`ok`/`failed`/`skipped`). A run with a failed collector exits 1.
- `.github/workflows/collect-hourly.yml`: cron `10 * * * *` plus manual trigger. It skips
  itself until the `DATABASE_URL` secret exists.
- District list is configurable: `jobs/config/districts.csv` or `DISTRICTS_FILE`.

**Checks**
| Done when | Result |
| --- | --- |
| After 3 hourly runs the DB has readings for all 10 cities | **Blocked**: no `DATA_GOV_IN_API_KEY` / `OPENAQ_API_KEY`, so `readings` is empty. Open-Meteo model air (1,152 rows) and weather (408 hours, 17 days) are stored for all 10 cities. The 3 runs were back to back, not an hour apart. |
| Missing hours appear as NULL rows with status "missing" | Pass in tests on recorded CPCB data and OpenAQ-shaped fixtures; not yet seen live |
| `fetch_log` shows no failed runs | Pass: 3 runs, Open-Meteo `ok`, CPCB/OpenAQ `skipped` (no key) |

Tests: backend 8 passed, jobs 48 passed (no live calls; Postgres test DB `vayukavach_test`).
ruff and ESLint clean. GitHub CI green on `1bfcc59`.

**Decisions and known issues**
- **CPCB feed values are AQI sub-indices, not concentrations** (recorded response: CO avg 63).
  They are stored with unit `aqi_subindex`. Phase 2 needs a decision on which source feeds the
  concentration-based AQI (see the open question in the Phase 1 summary).
- Hour keys use the **IST hour grid stored in UTC** (hh:30 UTC), not UTC-truncated hours, so
  CPCB, OpenAQ and Open-Meteo values line up for the same hour.
- The CPCB API's offset paging repeats records; we request 1,000 per page and de-duplicate.
  With a real key, check that no stations are lost across pages.
- OpenAQ fixtures follow the documented v3 shape; re-record once a key exists. The `bbox` query
  plus our own 25 km filter guards against coordinate-order mistakes.
- Open-Meteo has no NH₃ for India (CAMS global); stored as NULL model values.
- Secrets: httpx URL logging is silenced and error messages redact `api-key`, so keys never reach
  logs or `fetch_log.detail`.
- Weather and model rows are overwritten by newer runs (latest analysis/forecast wins);
  forecast-vs-actual history for Phase 8 may need a separate snapshot table.


## Phase 2: AQI calculator, completeness and shadow AQI — complete (2026-11-23)

**Built** (`backend/app/analysis/`, pure functions plus tests)
- `aqi_breakpoints.py`, `aqi.py`: India National AQI. CPCB breakpoints in one config file
  (lower bands checked against IES Arthapedia and PMC7397983; the Severe band's top is
  provisional). 24-h pollutants need at least 16 h; CO/O₃ use the 8-h running mean (daily
  mode: the day's max 8-h mean). An AQI needs at least 3 pollutants including PM. 24-h
  sub-index = **mean of hourly sub-indices** (CPCB's published method, see below).
- `completeness.py`: received / expected hours per station, pollutant and IST day; stations
  silent 3+ consecutive hours; hours when at least 25% of a city's stations were silent.
- `gap_bias.py`: missing rate in the 6 most polluted hours (CAMS PM2.5) vs the 6 cleanest;
  flag at 20 pp (configurable); PM readings at or near 999 µg/m³.
- `shadow.py`: inverse-distance fill from reporting stations within 15 km (with the CAMS
  difference term); 10% hold-out validation gives MAE, used as the ± band.
- `summary.py` → tables `daily_city_summary` (official vs measured vs shadow AQI,
  completeness, silence, gap flags, excluded counts) and `station_day_completeness`;
  `run.py summarize` (also in `hourly`). Real readings are never modified.
- `validate_cpcb.py` → `docs/validation/aqi_vs_cpcb.md`.

**Checks**
| Done when | Result |
| --- | --- |
| AQI matches CPCB's published values within a few points | **Mostly pass.** 40 Delhi station-hours: station AQI MAE 7.4 points, 90% within ±10. Per pollutant MAE: SO₂ 0.2, O₃ 1.1, NO₂ 1.7, PM10 3.6, CO 5.3, PM2.5 7.2 (bias +6.8). City level, Delhi today: CPCB 249, ours 250. Compared on station-hours, not "20 past station-days": the CPCB API has no history, so past days build up as we collect. |
| Completeness and gap flags for Delhi's recent days | Pass: 7 days of summaries; completeness 96–98% on full days, 1–5 stations silent 3+ h per day, no gap-bias flag this week (max +3.4 pp) |
| Shadow AQI validation reports an MAE | Pass: PM2.5 hold-out MAE 22–43 µg/m³ per day in Delhi (n = about 1,000 per day) |

Tests: backend 86 passed, jobs 57 passed; ruff and ESLint clean.

**What the CPCB comparison revealed (all fixed and documented in code)**
1. OpenAQ labels CPCB-network gases "ppb", but the values are µg/m³ (mg/m³ for CO). NO₂ was
   1.92× and SO₂ 2.63× too high (= MW/24.45). Fixed in the collector; migration 0004
   corrected stored rows.
2. CPCB's `last_update` is the end of the averaging hour, so the reading belongs to the hour
   before. Fixed; migration 0004 shifted stored CPCB rows.
3. CO/O₃: CPCB's running index uses the last 8 h, not the day's max 8 h.
4. CPCB's 24-h index averages the hourly sub-indices. PM2.5 error fell from 26.7 to 7.2 points.
   This method is now the default so that official vs shadow differences come from missing
   data, not from method (the textbook method stays available as `concentration_mean`).

**Known issues**
- PM2.5 is still about +7 points above CPCB; cause unknown (sensor choice or QA differences).
- Shadow AQI uses one CAMS value per district, so the model-difference term is 0 inside a
  city. Per-station CAMS cells would sharpen it (about 4 extra Open-Meteo calls per hour).
- The shadow ± band is narrow (±1–5) because only filled hours (2–3% in Delhi) carry the
  error; a Diwali-style night with many silent stations will widen it.
- Today's summary leaves out the newest 2 hours (OpenAQ publishing lag); the official figure
  uses the live CPCB feed.
- Only Delhi has OpenAQ history so far; the other cities show the official figure only until
  the backfill reaches them (about 2 more hourly runs). Shimla has no station at all.
- The Severe band's upper concentration limits are provisional (see `aqi_breakpoints.py`).


## Supabase (production database) — set up (2026-11-23)

- Project in ap-southeast-1. Apps connect through the **session pooler** (IPv4); the direct
  `db.<ref>.supabase.co` host is IPv6 only, which GitHub runners cannot reach.
- Migrations applied; **row level security on every table** (0005, plus each new table), so
  the public REST API with the publishable key reads nothing. A test enforces RLS on all tables.
- GitHub secrets `DATABASE_URL`, `DATA_GOV_IN_API_KEY`, `OPENAQ_API_KEY` set; "Collect hourly"
  now fills Supabase at :10 UTC (:40 IST). Local hourly runs were stopped so the two do not
  share the OpenAQ rate limit.
- Free tier is 500 MB: production backfills **30 days** of **reference monitors only**
  (`OPENAQ_BACKFILL_DAYS`, `OPENAQ_REFERENCE_ONLY` repository variables).

## Phase 3: Backend API — complete (2026-11-23)

**Built**
- `GET /api/v1/...`: `places/search`, `places/summary`; `air/{d}/now|hourly|daily|monthly|
  pollutants|stations|wind|advice`, `air/map?bbox=`; `weather/{d}/now|hourly|daily|sun|uv`;
  `heat/{d}`; `reports/{d}/gaps?date=&format=csv`. 18 endpoints plus `/health`; OpenAPI at `/docs`.
- Every response carries `source`, `updated_at` (IST), `label` (measured / estimated / mixed)
  and `stale` (older than 2 h). Pydantic response models throughout.
- `city_hour_aqi` table (filled by `summarize`): hour-by-hour CPCB official, our measured,
  shadow (± band) and CAMS AQI including forecast hours; vectorised running AQI
  (`analysis/hourly.py`, checked hour by hour against the scalar code).
- Districts without stations (Shimla) fall back to CAMS AQI, labelled Estimated.
- `analysis/heat.py`: NWS heat index, Stull wet-bulb (checked against a psychrometric solver),
  levels (draft thresholds), safe work windows 6 AM–7 PM, NDMA tips.
- CAMS CO₂ collected (ppm), shown as context only.
- In-memory TTL cache (5 min for DB, 1 h for the map grid, 24 h for geocoding), per-IP rate
  limit (120/min, `RATE_LIMIT_PER_MINUTE`), CORS for the frontend origin.

**Checks**
| Done when | Result |
| --- | --- |
| `/docs` lists all endpoints | Pass: 18 `/api/v1` paths in the OpenAPI schema (tested) |
| Every endpoint returns real stored data for the 10 cities | Pass: all 18 return 200 for all 10 cities on live data. Gap reports are `null` for the 9 cities whose OpenAQ backfill is still running (data, not an error) |
| Tests pass | Pass: backend 137 (18 endpoint tests on a seeded DB, external HTTP mocked), jobs 59 |

**Known issues**
- Air daily: days 6–10 are placeholders (`available: false`) until the Phase 8 outlook model.
- Air monthly has only 1 month of data so far; it fills as summaries accumulate.
- The CPCB "health impact" wording is CPCB's NAQI text as best known; confirm against the
  current CPCB bulletin before launch.
- The cache and rate limit are per process; use Redis if the API runs on several instances.


## Phase 4: Frontend shell and design system — complete (2026-11-23)

**Built** (`frontend/src`)
- Tokens: CSS variables (`index.css`) and the Tailwind theme: Outfit 300–600, text #17212B / #5E6B77,
  CPCB AQI colours, glass cards (white 90%, 14 px blur, 26 px radius, soft shadow), glass bubbles
  (78%, 10 px blur), accent #1F9D55, amber stale colour, sky background with clouds, heat
  gradient variables.
- Shell: `AppShell`, `IconRail` (74 px; Air, Temperature, Heat, Maps, Ask, plus Alerts and
  Profile; dark circle for the active tab; a bottom bar under 768 px), `Header` (location
  button left; weather, IST clock and data label right), `PlacesDrawer` (covered cities with
  AQI and temperature, Open-Meteo search marking uncovered places; closes on X, Escape, outside
  click or choosing; focus trapped while open and returned to the button), original logo.
- Shared UI: Card, MetricBubble, Pill, Tabs (ARIA, arrow keys), Skeleton, EmptyState ("No
  reading for this hour"), EstimatedBadge (dashed), MeasuredBadge, StaleBadge (amber "Updated
  3 h ago").
- Routing: `/air`, `/temperature`, `/heat`, `/finder`, `/ask` (plus `/alerts`, `/profile`);
  the place lives in `?place=` and localStorage. Data: TanStack Query, `VITE_API_BASE_URL`.
- Backend: `GET /api/v1/places/districts` for the drawer.
- Air tab preview: live AQI / main pollutant / visibility / completeness bubbles.

**Checks**
| Done when | Result |
| --- | --- |
| Switch tabs | Pass: Vitest + Chromium; `?place=` kept across tabs |
| Open and close Places | Pass: opens only from the location button; closes on X, Escape, outside click |
| Choose a city; survives a page refresh | Pass: URL and localStorage updated; a reload and a fresh visit without `?place=` keep the city (Chromium) |

Tests: frontend 10 (Vitest, in CI now), backend 138, jobs 59. Lint and type checks clean, no
browser console errors. Check it at http://localhost:5180 (API on :8000).

**Known issues**
- The Air tab is a preview: the map, charts and cards come in Phase 5.
- Bubbles stack one per row on phones; Phase 5 lays them out over the map.
- Playwright Chromium is installed for screenshots; end-to-end tests come in Phase 12.

### Collector hosting update (2026-11-23)
First Supabase run: Open-Meteo, OpenAQ (770 sensors, all 10 cities, 554,400 readings, 30 days),
and summaries OK; database 116 MB. **CPCB failed from GitHub:** data.gov.in refuses connections
from GitHub-hosted runners (works from India in about 1 s). Decision: CPCB runs hourly from the
Mac via launchd (`jobs/scripts/install_cpcb_launchd.sh`); GitHub runs the new `cloud` group.
Verified: launchd run stored 3,964 CPCB rows in Supabase. Limitation: no CPCB data while the
Mac sleeps (stored as missing hours).


## Phase 5: Air tab — complete (2026-11-23)

**Built** (`frontend/src/components/air`, `pages/AirPage.tsx`)
- `PollutionMap` (Leaflet + OpenStreetMap, greyscale light tiles): blurred PM2.5 zones from the
  CAMS grid, CPCB station pins (solid ring = measured, dashed = estimated from neighbours, grey
  "!" = not reporting) with tooltips, green city pin, legend, layer / zoom / recentre buttons
  (44 px), OSM and CAMS credits.
- Floating `MetricBubble`s over the map (2×2 grid under the map on phones): AQI + category +
  source (CPCB / Stations / Model), main pollutant, visibility (Estimated), data completeness
  with shadow AQI and band.
- `AqiChart` (hand-made SVG; Hourly / 10 days / Monthly): category-coloured bars, dashed outline
  where the official reading is missing (shadow value), faded dashed forecast, "Now" line,
  floating low–high bars with outlook placeholders, monthly bars with the current month
  outlined; y axis 0–500; legend with words; per-bar hover tooltip; table view; scrolls
  sideways on phones.
- `PollutantBars` (30-segment bars to sub-index/500, Measured/Estimated, "No reading", CO₂ as
  context), `WindCompass` (speed, gusts, direction, dispersion note), dark `HealthAdvice` (CPCB
  wording + "Find cleaner air"), `SourceList` (empty state until Phase 9).
- Colour accessibility: CPCB colours are mandated but fail colour-blind separation
  (Satisfactory vs Moderate) and contrast on white (dataviz validator), so category words and
  numbers always accompany colour, light bars get a darker outline, and the chart has a table view.

**Fixes found while testing**
- Station 24-h / 8-h averages now use settled hours (OpenAQ lag); before, Delhi's CO/O₃ fell
  back to the model.
- Hourly `updated_at` uses the freshest value of any kind (model-only districts were "stale").
- Map grid: Open-Meteo counts each point as a call, so 5×5 points on a fixed box per district
  (shared 1-hour cache) instead of 7×7 per viewport. API rate limit raised to 300/min (one page
  load is about 10 calls).
- A failed request now says "Couldn't load", never "No reading for this hour".

**Checks**
| Done when | Result |
| --- | --- |
| Air tab shows live stored data for any of the 10 cities | Pass: Chromium, all 10 cities fully loaded (AQI, 7 pollutants, chart), no console errors |
| All three chart tabs work | Pass (Vitest + screenshots) |
| Looks right on a laptop and a phone | Pass: 1440×900 and 390×844 checked against ref-04 / ref-06 |

Tests: frontend 16, backend 138, jobs 59.

**Known issues**
- Pollution Sources is empty until Phase 9; days 6–10 empty until Phase 8.
- Delhi has 82 pins and is busy at city zoom; clustering could come later.
- The OpenAQ hourly run makes about one request per live sensor (~770, ~14 min). A
  `/locations/{id}/latest` approach would cut that sharply (optimisation for later).


## Phase 6: Temperature tab — complete (2026-11-23)

**Built** (`frontend/src/components/temperature`, `pages/TemperaturePage.tsx`)
- Header row: "Temperature" pill, "Export CSV" (dark button). The global location button stays.
- `MyLocationCard`: condition with sky icon (moon after sunset), current temperature, today's
  high and low, original light-grey skyline drawing.
- `FeelsLikeCard`: apparent temperature + rule-based reason, link "Heat risk: <level> → Heat alerts".
- `TempTrend`: 13 bubbles 7 AM–7 PM positioned by value; the current hour is a green "Now"
  bubble with a soft stem (the number is already on the location card); forecast hours dashed.
- `ForecastList`: 10 days from **tomorrow** (today's high/low are on the location card),
  low–high gradient bars on one shared scale.
- `SunArc`, `UvGauge` (WHO bands, pointer, peak, cover-up hours), `ConditionGrid` (rainfall,
  humidity, dew point, pressure; segmented rows for cloud cover, rain chance and day–night swing
  with one-line notes).
- Each number appears once per screen; the header hides its temperature on this tab.
- CSV: one table (`kind` = hourly | daily), 18 columns, IST times, missing values left empty.
- Backend: `/weather/{d}/daily?days=` (1–16); feels-like reason only mentions sun when UV ≥ 3.

**Checks**
| Done when | Result |
| --- | --- |
| Every card shows real stored forecast data | Pass: Chromium, all 10 cities (location, 13 trend points, 10 forecast days) |
| Export CSV downloads a valid file | Pass: 48 hourly + 11 daily rows, 18 columns; unit-tested escaping and empty missing values |
| Switching places updates everything | Pass: Delhi → Shimla in Chromium |

Tests: frontend 22, backend 140, jobs 59.

**Known issues**
- Weather values are model values; the tab says so once at the top (and per card when stale)
  rather than putting dashed borders on every card.
- "Feels like" can equal the air temperature (different measures, so both are shown).


## Phase 7: Heat tab — complete (2026-11-23)

**Built**
- Backend (from Phase 3, now with consistency tests): NWS heat index, Stull wet-bulb, levels
  (draft thresholds in `analysis/heat.py`), safe windows 6 AM–7 PM, NDMA tips.
- `pages/HeatPage.tsx` + `components/heat/HeatParts.tsx`: full-page radial gradient by
  level, animated with registered CSS properties (respects reduced motion); big feels-like in
  DotGothic16; level, district and work-rest instruction; Safe work hours day arc (solid = safe,
  dotted in the level colour = take care, dot = now); hour-by-hour strip (rest of today);
  10-day heat forecast (today + 9) with level pills and range bars; Heat stress (air
  temperature, heat index, wet-bulb, humidity); UV; What to do today (NDMA tips + "Find cooler
  places"). The header hides its temperature on this tab.
- Contrast: the spec's light centres give white text 2.1:1 (#38BDF8) and 1.4:1 (#FCD34D), so
  centres are darkened (5.0–8.3:1) with the light colour kept as an outer glow; cards are 38%
  black glass. A unit test enforces >= 4.5:1 for every level, centre, edge and glow (it caught
  the Caution glow at 3.7:1, now fixed).

**Checks**
| Done when | Result |
| --- | --- |
| Heat calculations pass their tests | Pass: formula tests (NWS table, hand-worked regression, psychrometric reference) + API tests |
| Page colour changes with the level | Pass: Vitest (Normal / Danger / Extreme set the CSS variables) + Chromium screenshots of all four levels (non-Normal via a mocked API response) |
| Safe work hours match hourly data | Pass: API test rebuilds the windows from the hourly levels; live Chennai shows Caution 10 AM–2 PM and windows 6–10 AM, 2–7 PM |

Tests: frontend 32, backend 142, jobs 59. All 10 cities load with no console errors.

**Known issues**
- In November every city is Normal or Caution, so Danger/Extreme are verified with mocked
  responses; real summer data will exercise them.
- Level thresholds are a draft pending the district heat action plans.
- "Send alert to my team" waits for the Telegram bot (Phase 12).


## Phase 8: AQI forecasts — complete (2026-11-23)

**Built**
- History (`jobs/collectors/history.py`, `run.py history`): daily city AQI from OpenAQ
  daily means (one request per live sensor; 5,597 city-days, 9 cities, Jan 2025 → yesterday;
  Shimla has no station) and daily CAMS + weather features from Open-Meteo history, archive and
  forecast (7,070 district-days incl. 15 days ahead). Recent days are derived nightly from
  stored hourly readings with the same definition (`app/forecast/daily_aqi.py`).
- Tables (migration 0007, RLS): `city_daily_aqi`, `district_daily_features`,
  `aqi_forecast_daily`, `forecast_model`.
- Models (`app/forecast/model.py`):
  - Days 1–5: LightGBM correction of **all six** CAMS pollutants with the station value observed
    the day before the issue (and its 3-day mean), day ahead, calendar, Diwali / stubble flags
    and weather → India AQI. The day's range is the hourly CAMS shape centred on that value.
  - Days 6–10: LightGBM quantile regression (5 / 50 / 95%) on 7 days of lagged AQI, calendar,
    flags and target-day weather.
- Backtest: rolling weekly issues over 12 months, retrained before every issue on past data
  only; MAE and category hit rate per day; baselines raw CAMS, tomorrow = today, month
  average. Report `docs/models/backtest.md`, model card, notebook `docs/models/aqi_forecast.ipynb`.
- Serving (`app/forecast/serve.py`, `run.py forecast`, `.github/workflows/forecast-nightly.yml`
  at 03:07 IST): backtest gate → registry row with metrics → retrain → `aqi_forecast_daily`.
  Fallbacks: no gain → raw CAMS for days 1–5 / days 6–10 hidden; districts without station
  history stay on raw CAMS.
- API `/air/{d}/daily` serves the latest issue (median, low, high, method, model version);
  the 10-day chart shows ranges, a "most likely" tick and the method in the tooltip.
- Security: per-request headers, so the OpenAQ key is never sent to Open-Meteo (tested).

**Checks**
| Done when | Result |
| --- | --- |
| The backtest table exists | Pass: `docs/models/backtest.md` (48 weekly issues, 2025-11-20 → 2026-11-12) |
| Both models beat their baselines | Pass: days 1–5 MAE **19.3** vs raw CAMS 53.1 and tomorrow = today 24.7; days 6–10 MAE **21.1** vs tomorrow = today 27.9 and month average 24.6 |
| The 10-day chart uses the served forecasts | Pass: Air tab (Chromium) shows the served ranges, medians and methods; Shimla shows raw CAMS and no outlook |

Tests: backend 153, jobs 60, frontend 32.

**Known issues**
- The days 1–5 backtest uses CAMS analyses (no free archive of past forecasts): an upper bound.
- The outlook backtest uses observed weather; live serving uses the weather forecast.
- Outlook range coverage is 75% (target 80%); calibration is future work.
- The full nightly job takes about 7 minutes (52 weekly retrains).


## Phase 9: Pollution sources — complete (2026-11-24)

**Built**
- Table `source_shares` (migration 0008, RLS; unique on district/date/sector with
  `NULLS NOT DISTINCT` so static rows upsert). Sectors: the spec's list plus the ones the sources
  actually report (power plants, combined dust, diesel generators, brick kilns, sea salt,
  outside the city).
- Reviewed seed data in `backend/app/data/` (README explains each file):
  - `source_shares_studies.csv`: Lucknow, Kolkata, Hyderabad, Shimla and Mumbai from
    UrbanEmissions.info APnA city reports ("PM2.5 concentration: source-wise percentage share in
    2018"). The PDFs' text gives the numbers in pie order, not label order, so the values were
    read from the rendered charts (leader lines + APnA's fixed sector colours).
  - `delhi_dss_daily.csv`: IITM DSS "Fractional contribution to PM2.5 in Delhi" daily means for
    23–26 Nov 2026, entered manually.
- `run.py sources` loads both (checks every set sums to 100: ±0.5 for studies, ±1.5 for DSS,
  whose published values add up to ~101%).
- `GET /api/v1/air/{d}/sources`: latest daily DSS set (≤ 2 days old) else the study; scaled to
  exactly 100 with the published values kept; empty when there is no data.
- Air tab "Pollution Sources" card: icons, %, thin bars; subtitle "Today, IITM DSS",
  "IITM DSS, <date>" or "Study estimate, <year>"; source link; "No source data for this city yet".

**IITM DSS terms:** the site (ews.tropmet.res.in/dss) publishes no terms of use, no robots.txt and
no data API, and its pages take minutes to load. Per the spec, no automated collector: values
are entered manually from the Daily Mean page (procedure in `backend/app/data/README.md`).

**Checks**
| Done when | Result |
| --- | --- |
| Delhi shows a dated source breakdown | Pass: "Today, IITM DSS" (24 Nov 2026): transport 21.2%, outside the city 25.0%, … |
| At least 5 other cities show study-based shares with citations | Pass: Lucknow, Kolkata, Hyderabad, Shimla, Mumbai (APnA, 2018, linked) |
| Cities without data show the empty state | Pass: Kanpur, Chennai, Bengaluru, Patna (their APnA reports are not online) |

**Fixed along the way (from earlier phases)**
- The Places drawer opened **under** the map (Leaflet panes use z-index 400–700): the map now
  isolates its stacking context and the drawer sits on top (checked in Chromium).
- Tailwind opacity modifiers on theme colours (`bg-ink/20`, `border-ink-muted/40`, …) were
  silently dropped because the colours were CSS variables: theme colours now use RGB channels
  with `<alpha-value>` (drawer backdrop, estimated borders and badges now render).
- The Mac job also triggers the nightly forecast once a day (GitHub's schedule did not fire).

Tests: backend 159, jobs 60, frontend 33.

**Known issues**
- Delhi daily values need someone to enter them from the DSS page each day (or written
  permission from IITM for an automated collector); after 2 days without an entry Delhi shows
  no source data (there is no static Delhi study in the seed yet).
- Studies are 2018 model estimates; they are labelled as such.


## Phase 10: Clean Air and Cool Places Finder — complete (2026-11-24)

**Built**
- `GET /api/v1/finder?goal=air|heat&mode=nearby|daytrip|vacation&from=<district or lat,lon>`
  (`app/services/finder.py`):
  - Cleaner air: CPCB stations with a reading in the last 3 hours (≥ 3 pollutants incl. PM;
    Measured), one entry per town for day trips/vacations (its cleanest station), only places
    cleaner than here; 3-day CAMS outlook for the shortlist (Estimated); ranked by
    0.6 × today + 0.4 × outlook.
  - Cooler places: 28 hill stations (`app/data/hill_stations.csv`, coordinates from Open-Meteo
    geocoding, same-name places resolved by highest elevation: e.g. Mahabaleshwar 1,377 m, not a
    280 m namesake) + towns with CPCB stations; Open-Meteo 3-day "feels like" maxima; only places
    ≥ 1 °C cooler; ranked by closeness to a comfortable band (18–27 °C), then distance, so a snowy
    valley is not "best" in November.
  - Nearby heat returns an empty state: park/lake cooling needs satellite land-surface
    temperature, which VayuKavach does not have yet.
  - Places without data are dropped, never shown.
- `GET /api/v1/route?from=&to=`: OSRM public router (OpenRouteService when `ORS_API_KEY` is set),
  cached 24 h; distance, time, line, Google Maps navigation link.
- Precautions: CPCB health-impact wording (here and at the destination) or NDMA heat tips only.
- Frontend `/finder`: Cleaner air / Cooler place, Nearby / Day trip / Vacation cards (radios),
  "Use my location", ranked list (value chip, Measured/Estimated, ≈ travel time), map with start
  pin, numbered pins and the route line, route card with distance, time, value, next days,
  precautions and "Start navigation". Linked from the Air ("Find cleaner air") and Heat ("Find
  cooler places") tabs.

**Checks**
| Done when | Result |
| --- | --- |
| Each mode returns real ranked places with labels | Pass (Chromium, live data): air nearby/day trip/vacation 10 each (e.g. Kotputli AQI 56 from Delhi 234); heat day trip 5 and vacation 10 from Mumbai; heat nearby shows the empty state |
| Routes draw on the map | Pass: a route line in every mode (e.g. Delhi → Kotputli 167.8 km, 2 h 10 min) |
| No unlabelled or data-less place appears | Pass: every listed place carries Measured/Estimated; API test drops a place whose forecast is empty |

Tests: backend 167, jobs 60, frontend 37.

**Known issues**
- Rough list travel times assume 60 km/h; the route card shows the real time.
- Air candidates are CPCB stations only (OpenAQ low-cost sensors are not used for suggestions).
- Park- and lake-level cooling (satellite land-surface temperature) is future scope.

**Next:** Phase 11, Ask VayuKavach chatbot.
