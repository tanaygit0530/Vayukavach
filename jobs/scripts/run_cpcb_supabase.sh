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

# GitHub's own hourly schedule has not been firing reliably, so this job also asks GitHub to
# run the cloud collectors (Open-Meteo, OpenAQ, summaries) right after CPCB. Duplicate runs
# with the schedule are harmless: the workflow runs one at a time and writes with upserts.
REPO="$(git -C "$RUNTIME/repo" remote get-url origin | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"
if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  gh workflow run collect-hourly.yml -R "$REPO" -f job=cloud && echo "triggered cloud collection on $REPO"
  # The nightly forecast schedule is unreliable too: trigger it once a day, on the first run
  # after 03:00 IST (a marker file remembers the last day it was triggered).
  today="$(TZ=Asia/Kolkata date +%F)"
  if [[ "$(TZ=Asia/Kolkata date +%H)" -ge 3 && "$(cat "$RUNTIME/last_forecast" 2>/dev/null)" != "$today" ]]; then
    gh workflow run forecast-nightly.yml -R "$REPO" && echo "$today" > "$RUNTIME/last_forecast" \
      && echo "triggered nightly forecast on $REPO"
  fi
else
  echo "gh not logged in: collection relies on GitHub's schedules"
fi
