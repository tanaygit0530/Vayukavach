"""enable row level security

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-23 17:59:00.657363

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Supabase exposes every table in `public` through its REST API (PostgREST) to anyone with
# the publishable key. Row level security with no policies blocks that API completely; the
# backend and jobs connect as the table owner, which RLS does not restrict.
# Every new table must be added here or in a later migration (tests/test_models.py checks).

TABLES = (
    "alembic_version", "districts", "stations", "sensors", "readings", "model_air", "weather",
    "weather_daily", "fetch_log", "daily_city_summary", "station_day_completeness",
)  # fmt: skip


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
