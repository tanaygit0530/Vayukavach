"""Entry point for scheduled jobs: `uv run python run.py <job>`.

Collectors are registered here as they are built (Phase 1).
"""

import sys

JOBS: dict[str, object] = {}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in JOBS:
        print(f"usage: run.py <job>   available: {', '.join(sorted(JOBS)) or '(none yet)'}")
        return 0 if len(argv) < 2 else 1
    JOBS[argv[1]]()  # type: ignore[operator]
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
