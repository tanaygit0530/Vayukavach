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

## The problem

Every day Indians get one air-quality number, with no way to know whether it is complete. On
Diwali 2026, Delhi's monitoring stations went quiet exactly when the air was worst. And heat
alerts look at temperature alone, while humid heat is what harms outdoor workers.

**VayuKavach shows the official AQI, how complete the data behind it is, an estimate for the
missing hours, and clear advice on what to do: for air and heat, every season.**

---

## What it does

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

- **Air:** pollution map with station pins, official AQI next to a shadow AQI, data completeness,
  hourly · 10-day · monthly charts, pollutants, wind, pollution sources and CPCB health advice.
- **Temperature and Heat:** feels-like, heat index and wet-bulb, danger levels, safe work hours.
- **Finder:** cleaner-air and cooler places for a day trip or a vacation, with routes.
- **Ask VayuKavach:** a chatbot (Gemini) that answers only from VayuKavach's data, with sources,
  in English, Hindi and Marathi.
- **Alerts:** a 7 AM summary and instant alerts by WhatsApp or email.
- **Data reports:** completeness, silent stations and flagged hours per city and day, as CSV.

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

## The shadow AQI

When a station goes silent, the official AQI is computed from the stations that are left. If the
silent ones were the most polluted, the official number looks cleaner than the air.

```mermaid
flowchart TD
  A["Station-hour missing"] --> B{"Reporting stations<br/>within 15 km?"}
  B -- yes --> C["Estimate = inverse-distance weighted<br/>average of neighbours,<br/>shifted by the CAMS model difference"]
  B -- no --> D["Left empty<br/><i>never guessed, never zero</i>"]
  C --> E["Shadow AQI for the city"]
  E --> F["Confidence band<br/>= error measured by hiding 10%<br/>of real readings and estimating them"]
  F --> G["Shown NEXT TO the official AQI,<br/>never instead of it"]
```

---

## 10-day AQI forecast

```mermaid
flowchart LR
  H["History<br/>5,597 city-days<br/>Jan 2025 → yesterday"] --> BT["Rolling backtest<br/>48 weekly issues<br/>retrained each week"]
  BT --> G{"Beats its<br/>baselines?"}
  G -- yes --> S["Serve: days 1-5 corrected CAMS<br/>days 6-10 outlook (median + range)"]
  G -- no --> F["Fall back: raw CAMS,<br/>hide days 6-10"]
```

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

---

## Tech stack

| Layer | Tools |
|---|---|
| Data and jobs | Python 3.11, httpx, GitHub Actions, macOS launchd |
| Database | PostgreSQL on Supabase, SQLAlchemy 2 + Alembic |
| Analysis and ML | pandas, NumPy, LightGBM, scikit-learn |
| API | FastAPI |
| AI and alerts | Gemini 2.5 Flash (function calling), Twilio (WhatsApp, SMS), SMTP (email) |
| Frontend | React 19, Vite, TypeScript, Tailwind, TanStack Query, Leaflet + OpenStreetMap |
| Hosting | Vercel (frontend), Render (API), Supabase (database) |

---

## Run it locally

```bash
cp .env.example .env              # add your API keys
docker compose up -d db           # Postgres on localhost:5433

cd backend && uv sync && uv run alembic upgrade head
uv run uvicorn app.main:app --reload             # API → http://localhost:8000/docs

cd ../frontend && npm install && npm run dev     # app → http://localhost:5180
```

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
