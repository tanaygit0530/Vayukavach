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

## Checks

```bash
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd jobs     && uv run ruff check . && uv run pytest
cd frontend && npm run lint && npm run build
```

CI (`.github/workflows/ci.yml`) runs the same checks on every push.

## Data credits

Weather and air-model data: Open-Meteo (CC BY 4.0) and Copernicus CAMS. Maps: © OpenStreetMap contributors.
Official readings: CPCB via data.gov.in.
