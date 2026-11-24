"""Create a separate database with the synthetic Diwali day (tests/seed.py) for Playwright
end-to-end tests and offline demos.

    uv run python scripts/seed_e2e.py            # prints the DATABASE_URL and REPLAY_NOW to use

The database name gets an `_e2e` suffix, so the main database is never touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.testing import ensure_database, migrate, truncate_all  # noqa: E402
from tests.seed import NOW, seed_all  # noqa: E402


def e2e_url(base: str) -> str:
    url = make_url(base)
    if "supabase" in (url.host or "") or "pooler" in (url.host or ""):
        raise SystemExit("refusing to seed a hosted database: point DATABASE_URL at local Postgres")
    name = url.database or "vayukavach"
    return url.set(database=name if name.endswith("_e2e") else f"{name}_e2e").render_as_string(
        hide_password=False
    )


def main() -> None:
    url = e2e_url(get_settings().database_url)
    ensure_database(url)
    migrate(url)
    engine = create_engine(url)
    truncate_all(engine)
    seed_all(engine)
    engine.dispose()
    print(f"DATABASE_URL={url}")
    print(f"REPLAY_NOW={NOW.isoformat()}")


if __name__ == "__main__":
    main()
