from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.common import SRC_WEATHER, Meta, get_district, get_now, get_session, meta, to_ist
from app.models import District
from app.services import weather as wx

router = APIRouter(prefix="/heat", tags=["heat"])


class Window(BaseModel):
    from_hour: int  # IST clock hour
    to_hour: int


class HeatHourOut(BaseModel):
    hour: datetime
    local_hour: int
    temperature: float | None
    feels_like: float | None
    heat_index: float | None
    wet_bulb: float | None
    level: str | None


class HeatDay(BaseModel):
    date: date
    temperature_min: float
    temperature_max: float
    heat_index_max: float
    wet_bulb_max: float
    level: str | None
    is_forecast: bool


class Heat(Meta):
    district: str
    hour: datetime | None
    temperature: float | None
    humidity: float | None
    feels_like: float | None
    heat_index: float | None
    wet_bulb: float | None
    level: str | None
    level_name: str | None
    instruction: str | None
    worst_level_today: str | None
    safe_work_windows: list[Window]
    hourly: list[HeatHourOut]
    daily: list[HeatDay]
    tips: list[str]
    tips_source: str
    thresholds_status: str


@router.get("/{district}", response_model=Heat)
def heat(
    district: District = Depends(get_district),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    """Feels-like, heat index, wet-bulb, level, safe work hours (6 AM-7 PM IST) and NDMA tips."""
    data = wx.heat_report(session, district, now)
    return {
        **data,
        "district": district.slug,
        "hour": to_ist(data["hour"]),
        "hourly": [{**h, "hour": to_ist(h["hour"])} for h in data["hourly"]],
        **meta(
            f"{SRC_WEATHER}; heat index (NWS), wet-bulb (Stull 2011)",
            data["fetched_at"],
            "estimated",
            now,
        ),  # fmt: skip
    }
