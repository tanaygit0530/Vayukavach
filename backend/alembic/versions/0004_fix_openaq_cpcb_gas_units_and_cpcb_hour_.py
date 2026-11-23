"""fix openaq cpcb gas units and cpcb hour stamp

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-23 17:44:58.279733

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Rows stored before the collector fixes in this revision.
# 1) OpenAQ gas values from CPCB-network monitors were labelled ppb but are CPCB native units
#    (ug/m3; mg/m3 for CO). They were converted as ppb -> ug/m3 (x MW/24.45, CO also /1000).
#    Undo that conversion: native = stored * 24.45 / MW (x 1000 for CO).
# 2) CPCB `last_update` is the END of the averaging hour; readings move one hour earlier.

MW = {"no2": 46.01, "so2": 64.07, "co": 28.01, "o3": 48.00, "nh3": 17.03}


def _rescale(factor_sql: str) -> None:
    for pollutant, mw in MW.items():
        scale = 24.45 / mw * (1000 if pollutant == "co" else 1)
        op.execute(
            sa.text(
                f"UPDATE readings r SET value = r.value {factor_sql} :scale"
                " FROM sensors se, stations st"
                " WHERE se.station_id = r.station_id AND se.pollutant = r.pollutant"
                " AND st.id = r.station_id AND st.is_reference AND r.source = 'openaq'"
                " AND lower(se.unit) IN ('ppb', 'ppm') AND r.value IS NOT NULL"
                " AND r.pollutant = :p"
            ).bindparams(scale=scale, p=pollutant)
        )


def _shift_cpcb(interval: str) -> None:
    op.drop_constraint("uq_readings_station_hour_pol", "readings", type_="unique")
    op.execute(f"UPDATE readings SET hour = hour {interval} WHERE source = 'cpcb'")
    op.create_unique_constraint(
        "uq_readings_station_hour_pol", "readings", ["station_id", "hour", "pollutant"]
    )


def upgrade() -> None:
    _rescale("*")
    _shift_cpcb("- interval '1 hour'")


def downgrade() -> None:
    _shift_cpcb("+ interval '1 hour'")
    _rescale("/")
