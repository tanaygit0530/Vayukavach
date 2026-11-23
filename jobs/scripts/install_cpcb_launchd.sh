#!/bin/zsh
# Install (or update) the hourly CPCB launchd job for the current user.
# It runs at minute 5 of every hour while the Mac is awake; hours it misses are stored as gaps.
#   ./jobs/scripts/install_cpcb_launchd.sh            install / update
#   ./jobs/scripts/install_cpcb_launchd.sh uninstall  remove
# Needs SUPABASE_DATABASE_URL and DATA_GOV_IN_API_KEY in the repo's .env.
set -euo pipefail
LABEL="com.vayukavach.cpcb"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
RUNTIME="$HOME/.vayukavach"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$HOME/Library/Logs/vayukavach-cpcb.log"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [[ "${1:-}" == "uninstall" ]]; then
  rm -f "$PLIST"
  echo "removed $LABEL (runtime copy left in $RUNTIME)"
  exit 0
fi

value() { grep -E "^$1=" "$REPO_DIR/.env" | head -1 | cut -d= -f2- ; }
db="$(value SUPABASE_DATABASE_URL)"; key="$(value DATA_GOV_IN_API_KEY)"
[[ -n "$db" && -n "$key" ]] || { echo "set SUPABASE_DATABASE_URL and DATA_GOV_IN_API_KEY in .env" >&2; exit 1; }

mkdir -p "$RUNTIME" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
chmod 700 "$RUNTIME"
umask 077
printf 'DATABASE_URL=%s\nDATA_GOV_IN_API_KEY=%s\n' "$db" "$key" > "$RUNTIME/env"
origin="$(git -C "$REPO_DIR" remote get-url origin)"
if [[ -d "$RUNTIME/repo/.git" ]]; then
  git -C "$RUNTIME/repo" pull --ff-only --quiet
else
  git clone --quiet "$origin" "$RUNTIME/repo"
fi
cp "$REPO_DIR/jobs/scripts/run_cpcb_supabase.sh" "$RUNTIME/run_cpcb.sh"
chmod 700 "$RUNTIME/run_cpcb.sh"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/zsh</string><string>$RUNTIME/run_cpcb.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Minute</key><integer>5</integer></dict>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed $LABEL: runs at :05 every hour from $RUNTIME; log $LOG"
