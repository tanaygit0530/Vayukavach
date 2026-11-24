"""Delivery: email over SMTP (smtplib), SMS and WhatsApp over Twilio's REST API (httpx).

Never log message text or addresses: they are personal data."""

from __future__ import annotations

import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import httpx

from app.config import get_settings

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,24}$")
E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
TWILIO_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


class SendError(RuntimeError):
    """Delivery failed; the message is safe to show (no secrets, no address)."""


def normalise_address(channel: str, raw: str) -> str | None:
    """Email lower-cased; phones to E.164, with a bare 10-digit Indian mobile getting +91."""
    raw = (raw or "").strip()
    if channel == "email":
        return raw.lower() if EMAIL_RE.match(raw) else None
    digits = re.sub(r"[\s()-]", "", raw)
    if re.fullmatch(r"0?[6-9]\d{9}", digits):
        digits = "+91" + digits[-10:]
    elif re.fullmatch(r"91[6-9]\d{9}", digits):
        digits = "+" + digits
    return digits if E164_RE.match(digits) else None


def available() -> dict[str, bool]:
    s = get_settings()
    twilio = bool(s.twilio_account_sid and s.twilio_auth_token)
    return {
        "email": bool(s.smtp_host and s.smtp_from),
        "sms": twilio and bool(s.twilio_sms_from),
        "whatsapp": twilio and bool(s.twilio_whatsapp_from),
    }


def mask(channel: str, address: str) -> str:
    """For screens and logs: p***@gmail.com, +91******3210."""
    if channel == "email":
        user, _, domain = address.partition("@")
        return f"{user[:1]}***@{domain}"
    return address[:3] + "*" * max(len(address) - 7, 0) + address[-4:]


class Sender:
    """Sends through the configured services. Tests pass a fake with the same `send`."""

    def __init__(self, http: httpx.Client | None = None):
        self.http = http

    def send(self, channel: str, to: str, text: str, subject: str = "VayuKavach") -> None:
        if not available().get(channel):
            raise SendError(f"{channel} is not configured")
        if channel == "email":
            self._email(to, subject, text)
        else:
            self._twilio(channel, to, text)

    def _email(self, to: str, subject: str, text: str) -> None:
        s = get_settings()
        msg = EmailMessage()
        msg["From"] = formataddr(("VayuKavach", s.smtp_from))
        msg["To"] = to
        msg["Subject"] = subject
        msg["Message-ID"] = make_msgid(domain=s.smtp_from.partition("@")[2] or None)
        msg.set_content(text)
        try:
            if s.smtp_port == 465:
                server = smtplib.SMTP_SSL(
                    s.smtp_host, 465, context=ssl.create_default_context(), timeout=20
                )
            else:
                server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20)
                server.starttls(context=ssl.create_default_context())
            with server:
                if s.smtp_user:
                    server.login(s.smtp_user, s.smtp_password)
                server.send_message(msg)
        except (smtplib.SMTPException, OSError) as e:
            raise SendError(f"SMTP: {type(e).__name__}") from None

    def _twilio(self, channel: str, to: str, text: str) -> None:
        s = get_settings()
        if channel == "whatsapp":
            sender, to = s.twilio_whatsapp_from, f"whatsapp:{to}"
            if not sender.startswith("whatsapp:"):
                sender = f"whatsapp:{sender}"
        else:
            sender = s.twilio_sms_from
        http = self.http or httpx.Client()
        try:
            r = http.post(
                TWILIO_URL.format(sid=s.twilio_account_sid),
                auth=(s.twilio_account_sid, s.twilio_auth_token),
                data={"To": to, "From": sender, "Body": text},
                timeout=20.0,
            )
        except httpx.HTTPError as e:
            raise SendError(f"Twilio: {type(e).__name__}") from None
        if r.status_code >= 300:
            try:
                code = r.json().get("code")
            except ValueError:
                code = None
            # 63015/63016: WhatsApp sandbox not joined or outside the 24 h window
            raise SendError(f"Twilio HTTP {r.status_code} (code {code})")
