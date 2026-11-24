"""Send an operator notice to ADMIN_EMAIL / ADMIN_PHONE. Used by the uptime workflow.

uv run python -m app.alerts.notify "VayuKavach API is down"
"""

from __future__ import annotations

import sys

from app.alerts.channels import Sender, SendError
from app.alerts.service import admin_targets


def notify(text: str, sender=None) -> int:
    """Returns how many targets got the message."""
    sender = sender or Sender()
    sent = 0
    for channel, to in admin_targets():
        try:
            sender.send(channel, to, text, "VayuKavach: operator notice")
            sent += 1
        except SendError as e:
            print(f"{channel}: {e}", file=sys.stderr)
    return sent


if __name__ == "__main__":
    message = " ".join(sys.argv[1:]) or "VayuKavach operator notice"
    n = notify(message)
    print(f"notified {n} target(s)")
    raise SystemExit(0 if n else 1)
