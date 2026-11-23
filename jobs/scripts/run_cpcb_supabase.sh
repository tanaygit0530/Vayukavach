#!/bin/zsh
# Hourly CPCB collection into Supabase, from a machine in India (data.gov.in refuses
# GitHub-hosted runners). Started by launchd; see install_cpcb_launchd.sh.
# Runs from ~/.vayukavach (macOS blocks background jobs from reading ~/Desktop).
set -uo pipefail
RUNTIME="$HOME/.vayukavach"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
echo "== $(date '+%F %T %Z')"
set -a; source "$RUNTIME/env"; set +a
git -C "$RUNTIME/repo" pull --ff-only --quiet || echo "git pull failed; using the current copy"
cd "$RUNTIME/repo/jobs" || exit 1
uv sync --quiet --locked && uv run --quiet python run.py cpcb
