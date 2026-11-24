#!/usr/bin/env bash
# API for Playwright: a separate *_e2e database seeded with Diwali 2026 in Delhi, the clock
# pinned to 20:30 IST that night, and no AI keys or alert channels (rules chatbot, no sends).
set -euo pipefail
cd "$(dirname "$0")/../../backend"
eval "$(uv run --quiet python scripts/seed_e2e.py | sed 's/^/export /')"
export FRONTEND_ORIGIN=http://localhost:5190 PUBLIC_API_URL=http://localhost:8010
export GEMINI_API_KEY= OLLAMA_MODEL= ORS_API_KEY= SMTP_HOST= SMTP_FROM= TWILIO_ACCOUNT_SID= \
  TWILIO_AUTH_TOKEN=
exec uv run --quiet uvicorn app.main:app --port 8010
