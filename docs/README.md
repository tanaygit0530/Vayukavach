# VayuKavach

India's year-round environmental health shield: a daily air-quality and humid-heat risk view
for every district, plus a check on whether the official air data is complete.

Full product spec: [SPEC.md](SPEC.md) · Build plan: [VayuKavach Phase-wise Build Prompts.md](VayuKavach%20Phase-wise%20Build%20Prompts.md) · Progress: [PROGRESS.md](PROGRESS.md)

## Architecture

```text
 CPCB (data.gov.in) ─┐
 OpenAQ v3 ──────────┤   jobs/ (GitHub Actions, hourly)     backend/ (FastAPI)       frontend/ (React)
 Open-Meteo AQ/CAMS ─┼─► collectors ──► PostgreSQL ──► analysis: AQI, completeness, ──► /api/v1 ──► Air · Temperature
 Open-Meteo weather ─┘   (missing hours stored as rows)  gap bias, shadow AQI, heat           Heat · Finder · Ask
                                                                                    └──► Telegram alerts
```

| Folder | What it holds |
| --- | --- |
| `backend/` | FastAPI app (`app/`), SQLAlchemy models, Alembic migrations, analysis code, pytest tests |
| `jobs/` | Python collectors and scheduled jobs, run by GitHub Actions cron |
| `frontend/` | React + Vite + TypeScript + Tailwind app |
| `docs/` | Spec, build prompts, progress log, design references |

## Local setup

Prerequisites: Python 3.11, [uv](https://docs.astral.sh/uv/), Node 22+, Docker.

```bash
cp .env.example .env              # fill in API keys as phases need them
docker compose up -d db           # Postgres 16 on localhost:5433

cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload      # http://localhost:8000/health, docs at /docs

cd ../jobs && uv sync && uv run pytest

cd ../frontend
cp .env.example .env
npm install
npm run dev                               # http://localhost:5180
```

The Docker database uses host port **5433** so it does not clash with a local Postgres on 5432.

## Data pipeline (Phase 1)

```bash
cd jobs
uv run python run.py hourly         # cpcb, openmeteo-air, weather, openaq; each logged in fetch_log
uv run python run.py weather        # or any single collector
```

| Table | Filled by | Notes |
| --- | --- | --- |
| `districts` | `jobs/config/districts.csv` (override with `DISTRICTS_FILE`) | 10 starter cities |
| `stations`, `readings` | `cpcb`, `openaq` | One row per station, hour and pollutant. Missing data = `value NULL`, `status='missing'`, plus `reason` |
| `model_air` | `openmeteo-air` | CAMS model, past day + 5-day forecast (Estimated) |
| `weather`, `weather_daily` | `weather` | Past day + 16-day forecast |
| `fetch_log` | every collector | `ok`, `failed` or `skipped` (no API key) |

**Hour keys:** every `hour` is the start of an India (IST) clock hour, stored as a UTC
timestamp, so it falls at hh:30 UTC. CPCB, OpenAQ and Open-Meteo values for the same hour line up.

**CPCB values are AQI sub-indices**, not concentrations (unit `aqi_subindex`): that is what the
data.gov.in real-time feed publishes. Concentrations come from OpenAQ (µg/m³, CO in mg/m³).
CPCB's `last_update` is the **end** of the averaging hour, so a value stamped 16:00 IST is
stored for the hour starting 15:00 IST.

**OpenAQ units for CPCB-network stations:** OpenAQ labels their gases "ppb", but the numbers
are CPCB's native µg/m³ (mg/m³ for CO). The collector stores them as native units; other
providers are converted from ppb/ppm normally.

## Analysis (Phase 2)

| Module | What it does |
| --- | --- |
| `backend/app/analysis/aqi.py` | India National AQI: CPCB breakpoints, 24 h means (≥ 16 h), CO/O₃ 8 h (running or daily max), validity rule (≥ 3 pollutants incl. PM) |
| `completeness.py` | Received / expected hours per station, pollutant, day; stations silent 3+ h; hours with ≥ 25 % of a city's stations silent |
| `gap_bias.py` | "Missing when it mattered": missing rate in the 6 most polluted hours vs the 6 cleanest (flag at 20 pp); readings at or near 999 µg/m³ |
| `shadow.py` | Inverse-distance fill from stations within 15 km (+ CAMS difference), hold-out validation (MAE) used as the ± band |
| `summary.py` | Writes `daily_city_summary` (official vs measured vs shadow AQI) and `station_day_completeness`; run by `run.py summarize` |
| `validate_cpcb.py` | Compares our sub-indices with CPCB's published ones: `uv run python -m app.analysis.validate_cpcb docs/validation/aqi_vs_cpcb.md` |

**Storage:** a stored reading takes ~250 bytes with indexes. 90 days of 54 Delhi monitors
used 146 MB, and all 10 cities with low-cost sensors would pass Supabase's 500 MB free tier.
Production therefore defaults to `OPENAQ_BACKFILL_DAYS=30` and `OPENAQ_REFERENCE_ONLY=1`
(GitHub repository variables can override both).

**Security:** every table has row level security enabled with no policies (migration 0005),
so Supabase's public REST API cannot read or write them; the backend connects as the owner.

**Where each collector runs:** GitHub Actions runs the `cloud` group at :23 UTC (Open-Meteo, OpenAQ,
summaries) every hour. **CPCB runs on a Mac in India**, because data.gov.in refuses connections
from GitHub's runners (`Connection refused`, checked twice on 2026-11-23). Install it with
`./jobs/scripts/install_cpcb_launchd.sh`: a launchd job at :05 every hour, running from a clone
in `~/.vayukavach` (macOS blocks background jobs from reading `~/Desktop`), log in
`~/Library/Logs/vayukavach-cpcb.log`. Hours when the Mac is asleep are stored as missing.
After CPCB, the same job triggers the GitHub `cloud` collection with `gh workflow run`, because
GitHub's own hourly schedule did not fire reliably for this repository. It also triggers the
nightly forecast once a day (first run after 03:00 IST).

**Scheduled runs:** `.github/workflows/collect-hourly.yml` runs at minute 10 of every hour.
Add the repository secrets `DATABASE_URL` (Supabase), `DATA_GOV_IN_API_KEY` and `OPENAQ_API_KEY`;
until `DATABASE_URL` is set the workflow skips itself.

## API (Phase 3)

`cd backend && uv run uvicorn app.main:app --reload`, then open http://localhost:8000/docs.
Every response includes `source`, `updated_at` (IST), `label` and `stale`. Endpoints read only
stored data, except place search (Open-Meteo Geocoding) and the map grid (CAMS), which are cached.

## Checks

```bash
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd jobs     && uv run ruff check . && uv run pytest     # needs the docker Postgres
cd frontend && npm run lint && npm run build
```

CI (`.github/workflows/ci.yml`) runs the same checks on every push.

## Data credits

Weather and air-model data: Open-Meteo (CC BY 4.0) and Copernicus CAMS. Maps: © OpenStreetMap contributors.
Official readings: CPCB via data.gov.in.
