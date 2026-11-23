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

**Next:** Phase 1, hourly data pipeline.
