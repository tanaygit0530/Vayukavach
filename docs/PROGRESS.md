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


## Phase 1: Hourly data pipeline — built; live station data blocked on API keys (2026-11-23)

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

**Next:** Phase 2, AQI calculator, completeness and shadow AQI.
