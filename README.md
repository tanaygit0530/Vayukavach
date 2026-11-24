<div align="center">

<img src="docs/screenshots/logo.svg" width="72" alt="VayuKavach logo" />

# VayuKavach

### India's year-round environmental health shield

**Sameer tells you the AQI. VayuKavach tells you whether you can trust it, and what to do about it,**
**every season, in every district.**

**[Open the live app →](https://vayukavach-liart.vercel.app)** · [API docs](https://vayukavach-api.onrender.com/docs)
<sub>(free hosting: the first visit after a quiet hour can take about a minute to wake the API)</sub>

[![CI](https://github.com/tanaygit0530/Vayukavach/actions/workflows/ci.yml/badge.svg)](https://github.com/tanaygit0530/Vayukavach/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Supabase](https://img.shields.io/badge/Supabase-Postgres-3FCF8E?logo=supabase&logoColor=white)
![Leaflet](https://img.shields.io/badge/Leaflet-OpenStreetMap-199900?logo=leaflet&logoColor=white)
![Cost](https://img.shields.io/badge/running%20cost-₹0-1F9D55)

</div>

---

## The problem, in four numbers

| | |
|:--|:--|
| **376** | Delhi's average AQI on Diwali, 8 Nov 2026: the highest festival-day reading since 2021 |
| **10 of 59** | Delhi monitoring stations not reporting the next morning |
| **125** | station-hours missing from CPCB's record, released later by DPCC. **Every one was above 1,000 µg/m³** |
| **247 billion** | labour hours India lost to heat in 2024; 92% of the workforce is informal |

Today these data gaps are found only by journalists, by hand, after the fact. And heat alerts are
temperature-first, while humid heat is what harms outdoor workers.

> **In one line:** Indians get an environmental number every day, but no way to know if it is complete,
> and no clear instruction on what to do about it.

---

## What VayuKavach does

```mermaid
mindmap
  root((VayuKavach))
    Air Trust
      Data completeness score
      Missing-when-it-mattered detector
      Shadow AQI with confidence band
      Readings near the 999 cut-off
    Heat Shield
      Heat index and wet-bulb
      Safe work hours
      Morning worker alerts
    Unified view
      District map
      Hourly / 10-day / monthly AQI
      Data-gap reports for journalists
    Finder
      Cleaner-air trips
      Cooler places
    Ask VayuKavach
      Answers only from our data
```

| Module | What you get | Status |
|---|---|:-:|
| **Air Trust** | Official AQI **next to** a shadow AQI that fills missing hours, the share of readings that actually arrived, and a flag when gaps cluster in the most polluted hours | ✅ |
| **Air tab** | Pollution map, station pins (measured / estimated / silent), hourly · 10-day · monthly AQI, pollutants, wind, CPCB health advice | ✅ |
| **Pollution sources** | Share of PM2.5 by sector: IITM DSS daily for Delhi, APnA studies (2018) for 5 cities, honest empty state elsewhere | ✅ |
| **Temperature tab** | Feels-like with a reason, 7 AM–7 PM trend, 10-day forecast, sun arc, UV gauge, CSV export | ✅ |
| **Heat Shield** | Heat index + wet-bulb, Normal → Extreme colour-by-danger page, safe work windows, NDMA tips | ✅ |
| **Finder** | Cleaner-air and cooler places nearby, for a day trip or a vacation, with routes, travel time and official precautions | ✅ |
| **Ask VayuKavach** | A chatbot that answers only from VayuKavach's data, with sources | ✅ |
| **Alerts** | WhatsApp, SMS (Twilio) and email (SMTP): 7 AM summary and instant Very poor / Severe / Danger alerts, in English, Hindi and Marathi, confirmed with a code, one-click stop | ✅ |
| **Data reports** | Per city and day: completeness, silent stations, flagged hours, gap bias, station table, CSV download | ✅ |

---

## Diwali 2026, from our own data

The same checks, run on the stored hourly station data for Delhi (CPCB/SPCB stations via OpenAQ):

| | 8 Nov (Diwali) | 9 Nov (the morning after) |
|---|:-:|:-:|
| Expected hourly readings that arrived | 96% | 93% |
| Readings missing in the **6 most polluted** hours | 20.3% | **42.6%** |
| Readings missing in the 6 cleanest hours | 2.4% | 3.6% |
| *Missing when it mattered* flag (20+ points apart) | no (17.9) | **yes (39.0)** |
| PM readings at or near the 999 µg/m³ cut-off | 16 | 19 |
| AQI from the readings that arrived | 376 | 320 |
| Shadow AQI (missing hours estimated) | 380 (378–381) | **340 (336–342)** |

Across 10 cities and 28 days (25 Oct – 21 Nov), **8 city-days** were flagged, including Delhi on
3, 4 and 9 Nov and Mumbai on 27 Oct, 3 and 4 Nov. The report describes completeness only; it
does not say why readings were missing.

---

## How it works

```mermaid
flowchart LR
  subgraph SRC["Free data sources"]
    CPCB["CPCB real-time feed<br/>data.gov.in<br/><i>official sub-indices</i>"]
    OAQ["OpenAQ v3<br/><i>hourly concentrations</i>"]
    CAMS["Open-Meteo CAMS<br/><i>pollution model + forecast</i>"]
    WX["Open-Meteo weather<br/><i>16-day forecast</i>"]
  end

  subgraph COLLECT["Hourly collectors"]
    MAC["Mac in India · launchd<br/>:05 every hour"]
    GHA["GitHub Actions<br/>cloud group hourly<br/>+ nightly forecast"]
  end

  DB[("Supabase Postgres<br/>missing hours stored as rows<br/>row level security on")]

  subgraph AN["Analysis"]
    AQI["India AQI<br/>CPCB breakpoints"]
    COMP["Completeness<br/>+ silent stations"]
    GAP["Missing when<br/>it mattered"]
    SH["Shadow AQI<br/>inverse-distance fill"]
    HEAT["Heat index<br/>+ wet-bulb"]
  end

  API["FastAPI<br/>/api/v1 · 28 endpoints"]
  UI["React + Leaflet<br/>Air · Temperature · Heat<br/>Finder · Ask · Alerts · Reports"]
  LLM["Gemini 2.5 Flash<br/><i>may only call our tools</i>"]
  ALR["Alerts job<br/>hourly + 7 AM"]
  OUT["Email (SMTP)<br/>SMS · WhatsApp (Twilio)"]

  CPCB --> MAC
  OAQ --> GHA
  CAMS --> GHA
  WX --> GHA
  MAC --> DB
  GHA --> DB
  DB --> AN --> DB
  DB --> API --> UI
  API <--> LLM
  DB --> ALR --> OUT
```

**Why CPCB runs on a Mac:** data.gov.in refuses connections from GitHub's US servers (`Connection refused`,
tested twice), but answers from India in about a second. So a small launchd job on a Mac in India
collects CPCB every hour, and GitHub collects everything else.

### One hour in the pipeline

```mermaid
sequenceDiagram
  autonumber
  participant Mac as Mac (India)
  participant GH as GitHub Actions
  participant DB as Supabase
  participant U as You
  Note over Mac: :05 IST
  Mac->>DB: CPCB snapshot (~4,000 rows)<br/>+ a "missing" row for every station that stayed silent
  Note over GH: :40 IST
  GH->>DB: Open-Meteo air + weather (10 districts)
  GH->>DB: OpenAQ hourly values (770 sensors)
  GH->>DB: summarize: completeness, gap flags,<br/>official / measured / shadow / model AQI per hour
  U->>DB: open the app (via FastAPI, cached 5 min)
  DB-->>U: every number with source, time,<br/>Measured or Estimated, and a stale flag
```

---

## The shadow AQI, explained

When a station goes silent, the official AQI is computed from the stations that are left.
If the silent ones were the most polluted, the official number looks cleaner than the air.

```mermaid
flowchart TD
  A["Station-hour missing"] --> B{"Reporting stations<br/>within 15 km?"}
  B -- yes --> C["Estimate = inverse-distance weighted<br/>average of neighbours,<br/>shifted by the CAMS model difference"]
  B -- no --> D["Left empty<br/><i>never guessed, never zero</i>"]
  C --> E["Shadow AQI for the city"]
  E --> F["Confidence band<br/>= error measured by hiding 10%<br/>of real readings and estimating them"]
  F --> G["Shown NEXT TO the official AQI,<br/>never instead of it"]
```

| Signal | How it's computed |
|---|---|
| **Data completeness** | received hours ÷ expected hours, per station, pollutant and day |
| **Silent stations** | 3+ consecutive hours with nothing received |
| **City-wide silence** | hours when 25%+ of a city's stations were silent together |
| **Missing when it mattered** | missing rate in the 6 most polluted hours − missing rate in the 6 cleanest; flag at **20 points** |
| **Near the 999 cut-off** | PM readings ≥ 950 µg/m³; CPCB drops ≥ 999 from the AQI |

### How well does it work? Measured, including where it falls short

Hold-out test on 30 days of real station data in 9 cities
([full report](docs/validation/shadow_holdout.md), `backend/scripts/validate_shadow.py`):

| Test | Leaving the gaps out | Shadow estimate | Ratio-scaled prototype |
|---|:-:|:-:|:-:|
| Single hidden PM2.5 reading (8,025 readings) | – | 29.9 µg/m³ (32% of the level); a plain city average does as well (29.3) | – |
| City PM2.5 index, **random** gaps (250 city-days) | **1.1** AQI points | 3.6 | 2.2 |
| City PM2.5 index, **Diwali-style** gaps: the most polluted third of stations silent in the 6 worst hours | 10.7, **reads too clean** | 9.8 | **7.1** |

What this means:
- When gaps are random, the official average is already fine and filling only adds noise.
- When the most polluted stations go silent, leaving them out reads about 11 AQI points too
  clean. The shipped method recovers only 8% of that, because cleaner neighbours stand in for
  the silent stations.
- A prototype that scales each station by its usual ratio to the rest of the city that day
  recovers 34%. It is tested but not in the app yet.

---

## Checked against CPCB's own numbers

We compute India's AQI from raw station concentrations and compare it with the sub-indices CPCB
publishes for the **same stations and hours** (40 Delhi station-hours,
[full report](docs/validation/aqi_vs_cpcb.md)).

| Pollutant | Mean difference (AQI points) | Within ±10 |
|---|:-:|:-:|
| SO₂ | **0.2** | 100% |
| O₃ | **1.1** | 100% |
| NO₂ | **1.7** | 98% |
| PM10 | **3.6** | 92% |
| CO | **5.3** | 90% |
| PM2.5 | **7.2** | 92% |
| **Station AQI** | **7.4** | **90%** |

City level, Delhi: **CPCB 249 · our measured AQI 250 · shadow AQI 249.**

<details>
<summary><b>What the comparison taught us</b> (we started 31 points off)</summary>

| Finding | Effect | Fix |
|---|---|---|
| OpenAQ labels CPCB gases as **ppb**, but the numbers are **µg/m³** (mg/m³ for CO) | NO₂ 1.92× and SO₂ 2.63× too high, exactly the molecular-weight factor | Read as native units; data migration corrected stored rows |
| CPCB's `last_update` is the **end** of the averaging hour | Every window one hour late | Store the reading under the hour it closes |
| CPCB's running CO/O₃ index uses the **last 8 hours** | CO off by a constant 1.6× | Running 8-h mean for "now", daily max for days |
| CPCB's 24-h index **averages hourly sub-indices** | PM2.5 26.7 points off; the PM2.5 scale bends at 120 µg/m³ | Same method as CPCB, so official vs shadow differences come from missing data, not from maths |

</details>

---

## 10-day AQI forecast, tested on a year of history

```mermaid
flowchart LR
  H["History<br/>5,597 city-days<br/>Jan 2025 → yesterday"] --> BT["Rolling backtest<br/>48 weekly issues<br/>retrained each week"]
  BT --> G{"Beats its<br/>baselines?"}
  G -- yes --> S["Serve: days 1-5 corrected CAMS<br/>days 6-10 outlook (median + range)"]
  G -- no --> F["Fall back: raw CAMS,<br/>hide days 6-10"]
```

| Mean error (AQI points) | **Ours** | Raw CAMS | Tomorrow = today | Month average |
|---|:-:|:-:|:-:|:-:|
| Days 1–5 (CAMS corrected with yesterday's station data) | **19.3** | 53.1 | 24.7 | – |
| Days 6–10 (quantile outlook) | **21.1** | – | 27.9 | 24.6 |

The correction cuts raw CAMS's error by 64% and gets the CPCB category right 70–74% of the time
(raw CAMS: 40–47%). Retrained nightly; a model is only served if it beats its baselines.
Details, limits and the per-day table: [model card](docs/models/model-card.md) ·
[backtest](docs/models/backtest.md).

---

## Honesty rules, built in

```mermaid
flowchart LR
  N["Every number on screen"] --> S["has a source"]
  N --> T["has a time (IST)"]
  N --> L{"label"}
  L --> M["Measured<br/>solid ring"]
  L --> E["Estimated<br/>dashed ring"]
  N --> ST["older than 2 h?<br/>amber 'Updated 3 h ago'"]
  N --> Z["no data?<br/>'No reading for this hour'<br/>never a zero"]
```

- India's **National AQI** (0–500, CPCB breakpoints), never US or EU AQI.
- Missing data is **stored as data** (a row with a reason), never skipped.
- Neutral wording: **data completeness and reliability**, never blame.
- Districts without a station (Shimla) show a **model estimate, clearly labelled**.
- CPCB category colours are mandated but hard to tell apart for colour-blind readers, so the
  **category word and number always sit next to the colour**, and charts have a table view.

---

## Tested

| What | Result |
|---|---|
| Backend (pytest) | 277 tests; **94% coverage** on analysis, forecast, heat and alerts code (CI fails below 80%) |
| Collectors (pytest) | 60 tests, recorded API responses, no live calls |
| Frontend (Vitest + Testing Library) | 46 tests: every tab, loading / no-data / estimated / stale states |
| End to end (Playwright) | 6 journeys on desktop and a phone, against a seeded API replaying Diwali: switch tabs, Places drawer, chart tabs, chatbot, data report + CSV, alerts |
| Lighthouse, Air tab | Phone: performance **82**, accessibility **100**. Desktop: performance **96**, accessibility **100**, SEO 100 |
| Chatbot | 50-question evaluation in English, Hindi and Marathi: out-of-scope, medical, politics, cities not covered, dates with no data |

---

## Tech stack

| Layer | Tools |
|---|---|
| Data collection | Python 3.11, httpx + tenacity (retries, backoff, rate limits), GitHub Actions cron, macOS launchd |
| Database | PostgreSQL on Supabase (free tier), SQLAlchemy 2 + Alembic, row level security |
| Analysis & ML | pandas, NumPy, LightGBM (quantile + bias-correction models), scikit-learn: India AQI, completeness, gap bias, shadow AQI, heat index (NWS), wet-bulb (Stull 2011) |
| API | FastAPI, Pydantic models, TTL cache, per-IP rate limit, OpenAPI docs |
| AI | Gemini 2.5 Flash with function calling (only VayuKavach's tools), Ollama fallback, a rules engine when neither is available |
| Alerts | Python `smtplib` (email), Twilio REST API (SMS, WhatsApp), templates in en / hi / mr |
| Frontend | React 19, Vite, TypeScript, Tailwind, React Router, TanStack Query, Leaflet + OpenStreetMap, hand-made SVG charts |
| Quality | pytest (337 tests), Vitest (46) + Testing Library, Playwright e2e (desktop + phone), Lighthouse, coverage gate, ruff, ESLint, CI on every push |
| Hosting | Vercel (frontend), Render (API), Supabase (database), GitHub Actions (collectors, deploy after CI, hourly uptime check) |

---

## Project structure

```text
VayuKavach/
├── backend/            FastAPI app, models, migrations, analysis/, forecast/, chat/, alerts/, scripts/, tests
├── jobs/               Hourly collectors (CPCB, OpenAQ, Open-Meteo), run.py, launchd installer, tests
├── frontend/           React app: shell, every tab, shared UI, Vitest tests, e2e/ (Playwright, Lighthouse)
├── docs/               Spec, build plan, progress log, validation report, design references
└── .github/workflows/  CI, hourly collection, nightly forecast, deploy after CI, uptime check
```

---

## Run it locally

```bash
cp .env.example .env              # add DATA_GOV_IN_API_KEY and OPENAQ_API_KEY
docker compose up -d db           # Postgres on localhost:5433

cd backend && uv sync && uv run alembic upgrade head
uv run uvicorn app.main:app --reload             # API → http://localhost:8000/docs

cd ../jobs && uv sync && uv run python run.py hourly   # collect once

cd ../frontend && npm install && npm run dev     # app → http://localhost:5180
npm run e2e                                      # Playwright on a seeded copy (Diwali replay)
npm run lighthouse                               # Lighthouse thresholds on the Air tab
```

Optional keys in `.env`: `GEMINI_API_KEY` (chatbot), `SMTP_*` and `TWILIO_*` (alerts).
Deployment (Render + Vercel + GitHub settings): [docs/DEPLOY.md](docs/DEPLOY.md).
A 3-minute demo walk-through: [docs/DEMO.md](docs/DEMO.md).

Developer details (collectors, storage, hosting, API notes): [docs/README.md](docs/README.md)

---

## Limitations

- **Shadow AQI** recovers only part of the AQI hidden by Diwali-style gaps (see the measured
  results above); a better method is tested but not shipped.
- **Coverage:** 10 districts. Stations come from CPCB and OpenAQ only; low-cost sensors are not used.
- **CPCB history** starts on 22 Nov 2026, when collection began (the feed is a live snapshot);
  OpenAQ hourly data goes back to 24 Oct 2026 and daily data to Jan 2025.
- **Pollution sources:** IITM's Decision Support System has no terms of use, so Delhi's daily
  values are entered by hand; other cities use 2018 APnA studies.
- **Heat:** no satellite land-surface temperature yet, so park- and lake-level cooling is not shown.
- **Alerts:** WhatsApp runs on Twilio's sandbox (each person joins first). SMS to any Indian
  number needs DLT registration.
- **Free hosting:** Render's free plan sleeps without traffic (the first visit then
  waits about a minute), Gemini's free tier is rate-limited (the template engine answers then), and GitHub's
  hourly schedule is unreliable, so a Mac in India also triggers collection.

---

## Roadmap

```mermaid
gantt
  title Build phases
  dateFormat YYYY-MM-DD
  axisFormat %d %b
  section Data
  0 Setup and CI                 :done, 2026-11-23, 1d
  1 Hourly pipeline              :done, 2026-11-23, 1d
  2 AQI, completeness, shadow    :done, 2026-11-23, 1d
  3 Backend API                  :done, 2026-11-23, 1d
  section App
  4 Shell and design system      :done, 2026-11-23, 1d
  5 Air tab                      :done, 2026-11-23, 1d
  6 Temperature tab              :done, 2026-11-23, 1d
  7 Heat tab                     :done, 2026-11-23, 1d
  section Features
  8 AQI forecasts days 1-10      :done, 2026-11-23, 1d
  9 Pollution sources            :done, 2026-11-24, 1d
  10 Clean air and cool finder   :done, 2026-11-24, 1d
  11 Ask VayuKavach chatbot      :done, 2026-11-24, 1d
  12 Alerts, tests, deploy       :active, 2026-11-25, 2d
```

Progress log with checks for every phase: [docs/PROGRESS.md](docs/PROGRESS.md)

---

## Data and credits

| Source | Used for | Licence / terms |
|---|---|---|
| [CPCB real-time AQI](https://data.gov.in/resource/real-time-air-quality-index-various-locations) via data.gov.in | Official station sub-indices | Government Open Data Licence – India |
| [OpenAQ](https://openaq.org) | Hourly station concentrations | OpenAQ terms |
| [Open-Meteo](https://open-meteo.com) + [CAMS](https://atmosphere.copernicus.eu) | Pollution model, weather forecasts | CC BY 4.0 |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | Map tiles | © OpenStreetMap contributors (ODbL) |

<div align="center">
<sub>VayuKavach describes data completeness and reliability. It does not accuse anyone.</sub>
</div>
