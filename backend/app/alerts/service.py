"""Sign-up (verified by a one-time code), unsubscribe, and the hourly alert run.

Rules
- Daily summary: first run between 07:00 and 11:00 IST; once per IST day.
- Instant AQI alert: when the category enters Very poor or Severe, or gets worse within them.
  It re-arms only once air is back to Moderate or better, so a city hovering around the
  Poor/Very poor line does not get a message every hour.
- Instant heat alert: when the level reaches Danger or Extreme (or worsens); re-arms at Normal,
  so at most one heat alert per hot day.
- No instant alerts 22:00-06:00 IST; a crossing at night is sent at 06:00.
- Collector failures: the admin hears once when a collector's last two runs failed.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts import messages as msg
from app.alerts.channels import SendError, available, normalise_address
from app.analysis import heat as heatcalc
from app.analysis.time import IST
from app.config import get_settings
from app.models import AlertLog, AlertSubscription, District, FetchLog

log = logging.getLogger("vayukavach.alerts")

CODE_TTL = timedelta(minutes=15)
RESEND_AFTER = timedelta(seconds=60)
MAX_ATTEMPTS = 5
DAILY_FROM, DAILY_UNTIL = 7, 11  # IST hours
QUIET_FROM, QUIET_UNTIL = 22, 6


class AlertError(ValueError):
    """Shown to the person signing up (no secrets)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def stop_url(sub: AlertSubscription) -> str:
    return f"{get_settings().public_api_url.rstrip('/')}/api/v1/alerts/unsubscribe?t={sub.token}"


def _hash(token: str, code: str) -> str:
    return hashlib.sha256(f"{token}:{code}".encode()).hexdigest()


def _log(session: Session, sub_id: int | None, kind: str, channel: str, now, error=None) -> None:
    session.add(
        AlertLog(
            subscription_id=sub_id,
            kind=kind,
            channel=channel,
            sent_at=now,
            ok=error is None,
            error=(str(error)[:200] if error else None),
        )
    )


def subscribe(
    session: Session,
    sender,
    *,
    channel: str,
    address: str,
    district: District,
    language: str,
    daily: bool,
    instant: bool,
    now: datetime,
) -> tuple[AlertSubscription, str]:
    """Create or refresh a pending sign-up and send its code. Returns (sub, status) where
    status is "code_sent" or "already_subscribed" (a verified sign-up is not changed)."""
    if channel not in available() or not available()[channel]:
        raise AlertError("channel_unavailable", f"{channel} alerts are not set up yet")
    if not (daily or instant):
        raise AlertError("nothing_selected", "Choose the daily summary, instant alerts or both")
    addr = normalise_address(channel, address)
    if addr is None:
        raise AlertError(
            "bad_address",
            "Enter a valid email address" if channel == "email" else "Enter a valid mobile number",
        )
    sub = session.execute(
        select(AlertSubscription).where(
            AlertSubscription.channel == channel,
            AlertSubscription.address == addr,
            AlertSubscription.district_id == district.id,
        )
    ).scalar()
    if sub and sub.verified:
        return sub, "already_subscribed"
    if sub and sub.code_expires_at and now < sub.code_expires_at - CODE_TTL + RESEND_AFTER:
        raise AlertError("too_soon", "A code was just sent. Wait a minute before asking again.")
    if sub is None:
        sub = AlertSubscription(
            channel=channel,
            address=addr,
            district_id=district.id,
            token=secrets.token_urlsafe(32),
            created_at=now,
            verified=False,
        )
        session.add(sub)
    sub.language, sub.daily, sub.instant = language, daily, instant
    code = f"{secrets.randbelow(10**6):06d}"
    sub.code_hash = _hash(sub.token, code)
    sub.code_expires_at = now + CODE_TTL
    sub.code_attempts = 0
    session.flush()
    try:
        sender.send(
            channel,
            addr,
            msg.code_text(code, language),
            msg.subject("code", language, district.name),
        )
    except SendError as e:
        _log(session, sub.id, "verify", channel, now, e)
        session.commit()
        raise AlertError("send_failed", f"Could not send the code: {e}") from None
    _log(session, sub.id, "verify", channel, now)
    session.commit()
    return sub, "code_sent"


def verify(session: Session, sub_id: int, code: str, now: datetime) -> AlertSubscription:
    sub = session.get(AlertSubscription, sub_id)
    if sub is None or sub.verified or sub.code_hash is None:
        raise AlertError("not_found", "This sign-up was not found or is already confirmed")
    if sub.code_attempts >= MAX_ATTEMPTS:
        raise AlertError("locked", "Too many wrong codes. Ask for a new code.")
    if sub.code_expires_at is None or now > sub.code_expires_at:
        raise AlertError("expired", "The code has expired. Ask for a new code.")
    if not hmac.compare_digest(sub.code_hash, _hash(sub.token, (code or "").strip())):
        sub.code_attempts += 1
        session.commit()
        raise AlertError("wrong_code", "That code is not right")
    sub.verified, sub.code_hash, sub.code_expires_at = True, None, None
    session.commit()
    return sub


def unsubscribe(session: Session, token: str) -> bool:
    sub = session.execute(
        select(AlertSubscription).where(AlertSubscription.token == token)
    ).scalar()
    if sub is None:
        return False
    session.delete(sub)
    session.commit()
    return True


def _rank(order, level: str | None) -> int:
    return order.index(level) if level in order else -1


def aqi_due(prev: str | None, key: str) -> tuple[bool, str | None]:
    """(send?, level to remember)."""
    if key in msg.AQI_ALARM:
        if prev not in msg.AQI_ALARM or _rank(msg.AQI_ORDER, key) > _rank(msg.AQI_ORDER, prev):
            return True, key
        return False, prev
    if _rank(msg.AQI_ORDER, key) <= msg.AQI_ORDER.index("moderate"):
        return False, key  # re-arm
    return False, prev


def heat_due(prev: str | None, level: str) -> tuple[bool, str | None]:
    if level in msg.HEAT_ALARM:
        if prev not in msg.HEAT_ALARM or _rank(heatcalc.LEVELS, level) > _rank(
            heatcalc.LEVELS, prev
        ):
            return True, level
        return False, prev
    if level == "normal":
        return False, level
    return False, prev


@dataclass
class RunResult:
    sent: dict[str, int] = field(default_factory=lambda: {"daily": 0, "aqi": 0, "heat": 0})
    failed: int = 0
    admin: list[str] = field(default_factory=list)


def _deliver(session, sender, sub, kind: str, text: str, subj: str, now, result) -> bool:
    try:
        sender.send(sub.channel, sub.address, text, subj)
    except SendError as e:
        log.warning("alert %s to subscription %s failed: %s", kind, sub.id, e)
        _log(session, sub.id, kind, sub.channel, now, e)
        result.failed += 1
        return False
    _log(session, sub.id, kind, sub.channel, now)
    result.sent[kind] += 1
    return True


def run(session: Session, sender, now: datetime) -> RunResult:
    ist = now.astimezone(IST)
    quiet = ist.hour >= QUIET_FROM or ist.hour < QUIET_UNTIL
    in_daily = DAILY_FROM <= ist.hour < DAILY_UNTIL
    result = RunResult()
    air: dict[int, dict | None] = {}
    heat: dict[int, dict | None] = {}
    ids = (
        session.execute(select(AlertSubscription.id).where(AlertSubscription.verified.is_(True)))
        .scalars()
        .all()
    )
    for sub_id in ids:
        # lock one row at a time: the Mac and the cloud job may run at the same moment
        sub = session.execute(
            select(AlertSubscription)
            .where(AlertSubscription.id == sub_id)
            .with_for_update(skip_locked=True)
        ).scalar()
        if sub is None:
            continue
        d = session.get(District, sub.district_id)
        lang, url = sub.language, stop_url(sub)
        if sub.daily and in_daily and sub.last_daily_on != ist.date():
            text = msg.daily(session, d, lang, now, url)
            if _deliver(
                session, sender, sub, "daily", text, msg.subject("daily", lang, d.name), now, result
            ):
                sub.last_daily_on = ist.date()
        if sub.instant and not quiet:
            if d.id not in air:
                air[d.id] = msg.air_facts(session, d, now)
                heat[d.id] = msg.heat_facts(session, d, now)
            a, h = air[d.id], heat[d.id]
            if a:
                due, keep = aqi_due(sub.last_aqi_level, a["key"])
                if not due or _deliver(
                    session, sender, sub, "aqi", msg.aqi_alert(d, a, lang, url),
                    msg.subject("alert", lang, d.name), now, result,
                ):  # fmt: skip
                    sub.last_aqi_level = keep
            if h:
                due, keep = heat_due(sub.last_heat_level, h["level"])
                if not due or _deliver(
                    session, sender, sub, "heat", msg.heat_alert(d, h, lang, url),
                    msg.subject("alert", lang, d.name), now, result,
                ):  # fmt: skip
                    sub.last_heat_level = keep
        session.commit()
    result.admin = collector_failures(session, sender, now)
    return result


def collector_failures(session: Session, sender, now: datetime) -> list[str]:
    """Tell the admin once per failure streak when a collector's last two runs failed."""
    s = get_settings()
    targets = []
    if s.admin_email and available()["email"]:
        targets.append(("email", s.admin_email))
    if s.admin_phone:
        phone_channel = "whatsapp" if available()["whatsapp"] else "sms"
        if available()[phone_channel]:
            targets.append((phone_channel, normalise_address(phone_channel, s.admin_phone)))
    if not targets:
        return []
    alerted = []
    sources = (
        session.execute(
            select(FetchLog.source).where(FetchLog.started_at > now - timedelta(days=2)).distinct()
        )
        .scalars()
        .all()
    )
    for source in sorted(sources):
        last = (
            session.execute(
                select(FetchLog)
                .where(FetchLog.source == source, FetchLog.status.in_(("ok", "failed")))
                .order_by(FetchLog.started_at.desc())
                .limit(2)
            )
            .scalars()
            .all()
        )
        if len(last) < 2 or any(r.status != "failed" for r in last):
            continue
        kind = f"collector:{source}"
        already = session.execute(
            select(AlertLog.id).where(
                AlertLog.kind == kind, AlertLog.ok.is_(True), AlertLog.sent_at >= last[1].started_at
            )
        ).first()
        if already:
            continue
        text = (
            f"VayuKavach: collector '{source}' failed twice in a row "
            f"(last at {msg.fmt_time(last[0].started_at)}). Detail: {(last[0].detail or '-')[:300]}"
        )
        for channel, to in targets:
            try:
                sender.send(channel, to, text, f"VayuKavach: {source} collector failing")
                _log(session, None, kind, channel, now)
                alerted.append(source)
            except SendError as e:
                _log(session, None, kind, channel, now, e)
        session.commit()
    return sorted(set(alerted))
