"""Shared API pieces: response metadata, dependencies, caching, district lookup."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.time import IST
from app.config import get_settings
from app.db import SessionLocal
from app.models import District

STALE_AFTER = timedelta(hours=2)
Label = Literal["measured", "estimated", "mixed"]

SRC_CPCB = "CPCB via data.gov.in"
SRC_OPENAQ = "CPCB/SPCB stations via OpenAQ"
SRC_CAMS = "CAMS via Open-Meteo (CC BY 4.0)"
SRC_WEATHER = "Open-Meteo (CC BY 4.0)"
SRC_GEOCODING = "Open-Meteo Geocoding"


class Meta(BaseModel):
    """Present on every response: where the numbers come from and how fresh they are."""

    source: str = Field(description="Data source(s) for the numbers in this response")
    updated_at: datetime | None = Field(description="Time of the data, in IST")
    label: Label | None = Field(description="measured (stations) or estimated (model/filled)")
    stale: bool = Field(description="True when the data is older than 2 hours")


def meta(
    source: str, updated_at: datetime | None, label: Label | None, now: datetime
) -> dict[str, Any]:
    ist = updated_at.astimezone(IST) if updated_at else None
    stale = updated_at is None or (now - updated_at) > STALE_AFTER
    return {"source": source, "updated_at": ist, "label": label, "stale": stale}


def to_ist(ts: datetime | None) -> datetime | None:
    return ts.astimezone(IST) if ts else None


# ---------------------------------------------------------------- dependencies


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def get_now() -> datetime:
    replay = get_settings().replay_now
    return replay if replay is not None else datetime.now(UTC)


_http: httpx.Client | None = None


def get_http() -> httpx.Client:
    global _http
    if _http is None:
        _http = httpx.Client(
            timeout=20.0, headers={"User-Agent": "VayuKavach/0.1 (environmental health API)"}
        )
    return _http


def get_district(district: str, session: Session = Depends(get_session)) -> District:
    found = session.execute(select(District).where(District.slug == district.lower())).scalar()
    if found is None:
        raise HTTPException(status_code=404, detail=f"Unknown district '{district}'")
    return found


# ---------------------------------------------------------------- cache


class TTLCache:
    """Tiny thread-safe in-memory cache (swap for Redis when running several instances)."""

    def __init__(self, max_items: int = 2048):
        self._data: dict[Any, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self.max_items = max_items

    def get_or_set(self, key: Any, ttl: float, compute: Callable[[], Any]) -> Any:
        now = time.monotonic()
        with self._lock:
            hit = self._data.get(key)
            if hit and hit[0] > now:
                return hit[1]
        value = compute()
        with self._lock:
            if len(self._data) >= self.max_items:
                for k in [k for k, (exp, _) in self._data.items() if exp <= now] or list(
                    self._data
                )[: self.max_items // 4]:
                    self._data.pop(k, None)
            self._data[key] = (now + ttl, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


cache = TTLCache()
DB_TTL = 300  # data changes hourly; 5 minutes keeps responses fresh
EXTERNAL_TTL = 3600
GEOCODE_TTL = 24 * 3600
