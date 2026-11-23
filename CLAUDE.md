# VayuKavach: instructions for Claude Code

## Read first
- Full product spec: docs/SPEC.md (exported from the VayuKavach doc).
  The section "Implementation spec (latest design)" is the final design.
  Earlier design sections (illustrated and gradient styles) are background only.
- Phase-by-phase build prompts: "docs/VayuKavach Phase-wise Build Prompts.md"
- Content screenshots in docs/mockups/ (WHAT each screen must show; their styling is only a draft).
  Not yet added to the repo: fall back to SPEC.md for content.
- VISUAL TARGET in docs/references/: the finished UI must LOOK like these images (layout,
  card shapes, spacing, map style, floating bubbles, charts, colours, fonts, glass effect).
  Fill them with VayuKavach's content and data. Do not copy their brand names, logos or
  text (WeatherSwim, Cansaas, carbon offset, disputed items). Which reference to follow:
  - ref-02-heat-gradient.png: Heat tab look (colour gradient, dotted big number)
  - ref-04-air-map-dashboard.png: Air tab main reference (bubbles, AQI bars, sources, wind)
  - ref-05-temperature-analytics.png: Temperature tab reference
  - ref-06-map-bubbles.png: Air tab map zones and floating bubbles
  (ref-01 and ref-03 are not in the repo.)
- Look and layout: follow the reference image. Content, data and features: follow
  docs/mockups/ and SPEC.md. Keep India AQI colours and Measured/Estimated labels.
- Read only the SPEC sections the current phase needs.
- Progress so far: docs/PROGRESS.md

## Project
VayuKavach, India's year-round environmental health shield: air quality and heat risk for
every district, whether official air data is complete, estimates for missing data, and
clear advice on what to do.

## Stack
- Backend: Python 3.11, FastAPI, SQLAlchemy + Alembic, PostgreSQL (Supabase), pandas,
  scikit-learn, LightGBM, pytest
- Jobs: GitHub Actions cron (hourly collectors, nightly retrain)
- Frontend: React + Vite + TypeScript + Tailwind, React Router, TanStack Query,
  Leaflet + OpenStreetMap
- AI: Gemini API free tier (fallback Gemma via Ollama); alerts via Telegram Bot API
- Hosting: Vercel (frontend), Render or Railway (backend)

## Data sources (all free)
- CPCB real-time AQI via data.gov.in (resource 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69):
  current snapshot only, so store every hourly pull
- OpenAQ API v3: station history (60 req/min, 2,000 req/hour)
- Open-Meteo Air Quality (CAMS): pollutants + 5-day forecast, no key
- Open-Meteo Forecast, Historical and Geocoding APIs: weather, 16-day forecast, no key
- IITM Decision Support System: daily PM2.5 sources for Delhi only

## Rules (never break these)
- AQI is always India's National AQI (0-500, CPCB breakpoints), never US or EU AQI.
- Every number shown to users has a source, a timestamp and a Measured or Estimated label.
- Store missing data as rows (value NULL + reason); never skip, guess or show it as zero.
- Neutral wording: "data completeness" and "reliability", never "manipulation".
- Credit Open-Meteo, CAMS and OpenStreetMap on screen. Cache API calls; fetch hourly.
- Secrets only in .env; keep .env.example updated.
- Every calculation has unit tests.

## Design (light glass)
- Font Outfit; text #17212B / #5E6B77; cards white 88-92%, blur 14px, radius 26px
- AQI colours: Good #3BB44A, Satisfactory #A5D63F, Moderate #F5D547, Poor #F08A3C,
  Very poor #E5483F, Severe #9E1B32
- Left icon rail (Air, Temperature, Heat, Maps, Ask); bottom bar on phones
- Places drawer opens only from the location button
- Every component handles loading, no data, estimated and stale states
- Each number appears only once per screen

## Commands
- Backend: `cd backend && uv sync && uv run uvicorn app.main:app --reload` · tests `uv run pytest` · lint `uv run ruff check .`
- Migrations: `cd backend && uv run alembic upgrade head`
- Jobs: `cd jobs && uv sync && uv run pytest` · run collectors `uv run python run.py hourly`
- Frontend: `cd frontend && npm install && npm run dev` (http://localhost:5180) · lint `npm run lint` · build `npm run build`
- Database: `docker compose up -d db` (Postgres 16 on localhost:5433)

## How to work
- Show a plan before coding; wait for OK on big changes.
- Small commits per feature; run tests and lint before saying a step is done.
- Do not edit docs/SPEC.md, the build prompts or docs/mockups/ unless asked.
- If the spec is unclear, ask instead of guessing.
- No AI co-author / attribution lines in commits.

## End of every phase (always follow this)
1. Run all tests and lint; fix failures before going on.
2. Check every item in the phase's "Done when" list and report pass/fail for each.
3. For UI phases, start the app and give the URL to check against docs/references/.
4. Update docs/PROGRESS.md: what was built, test results, known issues, what is next.
5. Commit with the message "Phase N: <short summary>".
6. Give a short summary, then ASK: "Phase N is complete. Shall I continue to
   Phase N+1: <name>?" and STOP.
7. If a "Done when" item fails and cannot be fixed, say so clearly and ask what to do.
