"""Shared pieces for every collector: HTTP with retries, rate limits, run logging,
time and unit helpers, and bulk upserts."""

from __future__ import annotations

import math
import time
import traceback
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone

import httpx
from sqlalchemy import Table, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from tenacity import (
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.models import FetchLog

USER_AGENT = "VayuKavach/0.1 (open environmental health dashboard)"
IST_OFFSET = timedelta(hours=5, minutes=30)


# ---------------------------------------------------------------- time helpers


def utc_now() -> datetime:
    return datetime.now(UTC)


IST = timezone(IST_OFFSET, "IST")


def floor_hour(ts: datetime) -> datetime:
    """Start of the India (IST) clock hour containing `ts`, returned in UTC.

    Indian sources report on IST hour boundaries (CPCB '16:00' IST, Open-Meteo with
    timezone=Asia/Kolkata), which fall at hh:30 UTC. Every hour key in the database uses
    this grid so that readings, model values and weather for the same hour line up.
    """
    if ts.tzinfo is None:
        raise ValueError("naive datetime; attach a timezone first")
    return ts.astimezone(IST).replace(minute=0, second=0, microsecond=0).astimezone(UTC)


def hours_between(start: datetime, end: datetime) -> Iterator[datetime]:
    """UTC hours in [start, end)."""
    h = floor_hour(start)
    while h < end:
        yield h
        h += timedelta(hours=1)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------- units

# Molecular weights (g/mol) for ppb/ppm -> ug/m3 at 25 degC, 1 atm (molar volume 24.45 L).
MOLECULAR_WEIGHT = {"no2": 46.01, "so2": 64.07, "co": 28.01, "o3": 48.00, "nh3": 17.03}
MOLAR_VOLUME = 24.45


def _clean_unit(unit: str) -> str:
    return unit.strip().lower().replace("µ", "u").replace("μ", "u").replace("³", "3")


def to_standard_unit(pollutant: str, value: float, unit: str) -> tuple[float, str]:
    """Convert to the CPCB units: ug/m3 for everything except CO in mg/m3."""
    u = _clean_unit(unit)
    if u in {"ug/m3", "ugm3", "ug/m^3"}:
        ug = value
    elif u in {"mg/m3", "mgm3", "mg/m^3"}:
        ug = value * 1000.0
    elif u in {"ppb", "ppm"}:
        if pollutant not in MOLECULAR_WEIGHT:
            raise ValueError(f"cannot convert {unit} for {pollutant}")
        ppb = value * 1000.0 if u == "ppm" else value
        ug = ppb * MOLECULAR_WEIGHT[pollutant] / MOLAR_VOLUME
    else:
        raise ValueError(f"unknown unit {unit!r} for {pollutant}")
    if pollutant == "co":
        return ug / 1000.0, "mg/m3"
    return ug, "ug/m3"


# CPCB's AQI method drops readings at or above 999 ug/m3 (see SPEC, Air Trust module).
EXCLUSION_THRESHOLD = 999.0


def concentration_status(pollutant: str, value: float, unit: str) -> str:
    if unit == "ug/m3" and pollutant in {"pm25", "pm10"} and value >= EXCLUSION_THRESHOLD:
        return "excluded_over_999"
    return "ok"


# ---------------------------------------------------------------- HTTP


SECRET_PARAMS = {"api-key", "api_key", "apikey", "token", "key"}


def redact_url(url: httpx.URL | str) -> str:
    """URL with secret query parameters replaced, safe for logs and fetch_log."""
    u = httpx.URL(str(url))
    params = [(k, "***" if k.lower() in SECRET_PARAMS else v) for k, v in u.params.multi_items()]
    return str(u.copy_with(params=params)) if params else str(u)


class HTTPFailure(Exception):
    """Non-retryable HTTP error; the message never contains secrets."""

    def __init__(self, response: httpx.Response):
        super().__init__(f"HTTP {response.status_code} from {redact_url(response.request.url)}")
        self.status_code = response.status_code


class RetryableHTTPError(HTTPFailure):
    pass


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, RetryableHTTPError | httpx.TransportError)


@dataclass
class RateLimit:
    """Spacing between calls plus an optional cap on calls for this run."""

    per_minute: int | None = None
    budget: int | None = None
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    calls: int = 0
    _last: float | None = field(default=None, repr=False)

    @property
    def exhausted(self) -> bool:
        return self.budget is not None and self.calls >= self.budget

    def acquire(self) -> None:
        if self.exhausted:
            raise BudgetExhausted
        if self.per_minute and self._last is not None:
            gap = 60.0 / self.per_minute - (self.clock() - self._last)
            if gap > 0:
                self.sleep(gap)
        self._last = self.clock()
        self.calls += 1


class BudgetExhausted(Exception):
    """The run used its request budget; the rest continues next run."""


class HttpClient:
    """httpx client that retries timeouts, 429 and 5xx with exponential backoff."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        attempts: int = 5,
        max_wait: float = 60.0,
        rate_limit: RateLimit | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.client = client or httpx.Client(timeout=60.0)
        self.client.headers.update({"User-Agent": USER_AGENT, **(headers or {})})
        self.attempts = attempts
        self.max_wait = max_wait
        self.rate_limit = rate_limit or RateLimit()

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None):
        """GET JSON. `headers` apply to this request only (e.g. one provider's API key)."""
        retrying = Retrying(
            stop=stop_after_attempt(self.attempts),
            wait=wait_exponential(multiplier=1, min=1 if self.max_wait else 0, max=self.max_wait),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                self.rate_limit.acquire()
                response = self.client.get(url, params=params, headers=headers)
                if response.status_code == 429 or response.status_code >= 500:
                    raise RetryableHTTPError(response)
                if response.is_error:
                    raise HTTPFailure(response)
                return response.json()
        raise AssertionError("unreachable")


# ---------------------------------------------------------------- run logging


@dataclass
class RunStats:
    rows: int = 0
    errors: int = 0
    notes: list[str] = field(default_factory=list)
    skipped: bool = False


@contextmanager
def fetch_run(session: Session, source: str) -> Iterator[RunStats]:
    """Record one collector run in fetch_log, whatever happens inside it."""
    log = FetchLog(source=source, started_at=utc_now(), status="running")
    session.add(log)
    session.commit()
    stats = RunStats()
    try:
        yield stats
        session.commit()
        status = "skipped" if stats.skipped else "ok"
        detail = "; ".join(stats.notes) or None
    except Exception as exc:
        session.rollback()
        status = "failed"
        detail = "".join(traceback.format_exception_only(exc)).strip()[:2000]
        stats.errors += 1
        raise
    finally:
        session.execute(
            update(FetchLog)
            .where(FetchLog.id == log.id)
            .values(
                finished_at=utc_now(),
                rows=stats.rows,
                errors=stats.errors,
                status=status,
                detail=detail,
            )
        )
        session.commit()


# ---------------------------------------------------------------- upserts


def chunked(rows: Sequence[dict], size: int = 1000) -> Iterable[Sequence[dict]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def upsert(
    session: Session,
    table: Table,
    rows: Sequence[dict],
    conflict: Sequence[str],
    *,
    do_nothing: bool = False,
) -> int:
    """INSERT ... ON CONFLICT. Returns the number of rows written (inserted or updated)."""
    written = 0
    for chunk in chunked(rows):
        stmt = insert(table).values(list(chunk))
        if do_nothing:
            stmt = stmt.on_conflict_do_nothing(index_elements=list(conflict))
        else:
            cols = {c for row in chunk for c in row} - set(conflict)
            stmt = stmt.on_conflict_do_update(
                index_elements=list(conflict), set_={c: stmt.excluded[c] for c in cols}
            )
        # RETURNING gives an exact count (psycopg reports -1 rowcount for these).
        written += len(session.execute(stmt.returning(table.c.id)).all())
    return written
