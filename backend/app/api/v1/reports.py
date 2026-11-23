from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.analysis.time import ist_date
from app.api.common import SRC_OPENAQ, Meta, get_district, get_now, get_session, meta, to_ist
from app.models import District
from app.services import reports

router = APIRouter(prefix="/reports", tags=["reports"])


class GapBias(BaseModel):
    flagged: bool
    polluted_hours_missing_pct: float | None
    clean_hours_missing_pct: float | None
    difference_pp: float | None


class NearLimit(BaseModel):
    station_id: int
    name: str | None
    hour: datetime
    pollutant: str
    value: float | None
    at_or_over_999: bool


class StationCompleteness(BaseModel):
    station_id: int
    name: str
    pollutant: str
    expected: int
    received: int
    excluded: int
    pct: float
    longest_gap_hours: int


class GapReport(Meta):
    district: str
    date: date
    completeness_pct: float | None
    gap_bias: GapBias | None
    silent_stations: list[dict]
    city_silent_hours: list[datetime]
    readings_near_limit: list[NearLimit]
    stations: list[StationCompleteness]
    wording: str = "This report describes data completeness only. It does not assign blame."


@router.get("/{district}/gaps", response_model=GapReport)
def gaps(
    district: District = Depends(get_district),
    day: date | None = Query(default=None, alias="date", description="IST date, default today"),
    format: str = Query(default="json", pattern="^(json|csv)$"),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """Silent stations, flagged hours and per-station completeness for a day (JSON or CSV)."""
    day = day or ist_date(now)
    data = reports.gap_report(session, district, day, now)
    if format == "csv":
        return Response(
            reports.gap_csv(data),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="vayukavach-gaps-{district.slug}'
                f'-{day}.csv"'
            },
        )
    return {
        **data,
        "district": district.slug,
        "silent_stations": [
            {**s, "from": to_ist(s["from"]), "to": to_ist(s["to"])} for s in data["silent_stations"]
        ],
        "city_silent_hours": [to_ist(h) for h in data["city_silent_hours"]],
        "readings_near_limit": [
            {**r, "hour": to_ist(r["hour"])} for r in data["readings_near_limit"]
        ],  # fmt: skip
        **meta(SRC_OPENAQ, data["computed_at"], "measured", now),
    }
