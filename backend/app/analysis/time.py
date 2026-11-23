"""India-day helpers. Hours are IST clock hours stored as UTC (hh:30 UTC)."""

from datetime import UTC, date, datetime, time, timedelta, timezone

import pandas as pd

IST = timezone(timedelta(hours=5, minutes=30), "IST")


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """UTC [start, end) of an India (IST) calendar day."""
    start = datetime.combine(day, time(0), tzinfo=IST).astimezone(UTC)
    return start, start + timedelta(days=1)


def day_hours(day: date, now: datetime | None = None) -> pd.DatetimeIndex:
    """Hour starts of an IST day; for today, only hours that have fully ended."""
    start, end = day_bounds(day)
    hours = pd.date_range(start, end, freq="1h", inclusive="left")
    if now is not None:
        hours = hours[hours + timedelta(hours=1) <= now]
    return hours


def ist_date(ts: datetime) -> date:
    return ts.astimezone(IST).date()
