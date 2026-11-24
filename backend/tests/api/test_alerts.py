import re
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.alerts import channels, messages, service
from app.alerts.channels import Sender, SendError, mask, normalise_address
from app.alerts.service import aqi_due, heat_due
from app.analysis.time import day_bounds
from app.api.v1 import alerts as alerts_api
from app.config import get_settings
from app.models import AlertLog, AlertSubscription, District, FetchLog
from tests.analysis.helpers import DAY
from tests.api.conftest import NOW


class FakeSender:
    def __init__(self, fail: bool = False):
        self.sent: list[tuple[str, str, str, str]] = []
        self.fail = fail

    def send(self, channel, to, text, subject="VayuKavach"):
        if self.fail:
            raise SendError("Twilio HTTP 400 (code 63015)")
        self.sent.append((channel, to, text, subject))


@pytest.fixture
def configured(monkeypatch):
    """Fake credentials only: nothing here can reach a real SMTP server or Twilio."""
    for k, v in {
        "SMTP_HOST": "smtp.test",
        "SMTP_FROM": "alerts@vayukavach.test",
        "SMTP_USER": "user",
        "SMTP_PASSWORD": "pw",
        "TWILIO_ACCOUNT_SID": "ACtest",
        "TWILIO_AUTH_TOKEN": "tok",
        "TWILIO_SMS_FROM": "+15550001111",
        "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
        "PUBLIC_API_URL": "https://api.vayukavach.test",
    }.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def session(seeded, db_engine):
    with Session(db_engine) as s:
        yield s


@pytest.fixture
def fake(client):
    sender = FakeSender()
    from app.main import app

    app.dependency_overrides[alerts_api.get_sender] = lambda: sender
    alerts_api.signup_limiter.clear()
    alerts_api.verify_limiter.clear()
    return sender


# ------------------------------------------------------------------ pure rules


@pytest.mark.parametrize(
    "channel,raw,want",
    [
        ("sms", "98765 43210", "+919876543210"),
        ("sms", "09876543210", "+919876543210"),
        ("whatsapp", "+91 98765-43210", "+919876543210"),
        ("whatsapp", "919876543210", "+919876543210"),
        ("sms", "+14155550123", "+14155550123"),
        ("sms", "12345", None),
        ("sms", "5876543210", None),  # Indian mobiles start with 6-9
        ("email", " Priya.S@Example.COM ", "priya.s@example.com"),
        ("email", "no-at-sign.com", None),
        ("email", "a@b", None),
    ],
)
def test_addresses_are_normalised(channel, raw, want):
    assert normalise_address(channel, raw) == want


def test_addresses_are_masked():
    assert mask("email", "priya@gmail.com") == "p***@gmail.com"
    assert mask("sms", "+919876543210") == "+91******3210"


@pytest.mark.parametrize(
    "prev,now,send,keep",
    [
        (None, "poor", False, None),
        (None, "verypoor", True, "verypoor"),
        ("poor", "verypoor", True, "verypoor"),
        ("verypoor", "verypoor", False, "verypoor"),
        ("verypoor", "severe", True, "severe"),
        ("severe", "verypoor", False, "severe"),
        ("severe", "poor", False, "severe"),  # hovering: not re-armed yet
        ("severe", "moderate", False, "moderate"),  # re-armed
        ("moderate", "severe", True, "severe"),
    ],
)
def test_aqi_alert_fires_on_entering_very_poor_and_rearms_at_moderate(prev, now, send, keep):
    assert aqi_due(prev, now) == (send, keep)


@pytest.mark.parametrize(
    "prev,now,send,keep",
    [
        (None, "caution", False, None),
        ("normal", "danger", True, "danger"),
        ("danger", "danger", False, "danger"),
        ("danger", "extreme", True, "extreme"),
        ("danger", "caution", False, "danger"),
        ("danger", "normal", False, "normal"),
    ],
)
def test_heat_alert_fires_at_danger_and_rearms_at_normal(prev, now, send, keep):
    assert heat_due(prev, now) == (send, keep)


# ------------------------------------------------------------------ messages


@pytest.mark.parametrize("lang,word", [("en", "Air:"), ("hi", "हवा:"), ("mr", "हवा:")])
def test_daily_message_has_source_time_and_label_for_every_number(session, lang, word):
    delhi = session.execute(select(District).where(District.slug == "delhi")).scalar_one()
    text_ = messages.daily(session, delhi, lang, NOW, "https://x/stop")
    assert word in text_ and "https://x/stop" in text_
    numbered = [line for line in text_.splitlines() if re.search(r"AQI \d+|\d+°C", line)]
    assert len(numbered) == 2, text_  # air and heat both have data in the seed
    for line in numbered:
        assert "IST" in line, line
        assert any(v[lang] in line for v in (messages.L["measured"], messages.L["estimated"]))
        assert "CPCB" in line or "OpenAQ" in line or "Open-Meteo" in line, line


def test_alert_texts_are_localised():
    d = District(name="Delhi", slug="delhi")
    a = {"aqi": 342, "key": "verypoor", "category": "Very poor", "main": "pm25",
         "source": "CPCB via data.gov.in", "time": NOW, "label": "measured"}  # fmt: skip
    en = messages.aqi_alert(d, a, "en", "u")
    assert "Very poor (AQI 342)" in en and "CPCB via data.gov.in" in en and "Measured" in en
    hi = messages.aqi_alert(d, a, "hi", "u")
    assert "दिल्ली" in hi and "बहुत खराब" in hi and "मापा गया" in hi
    h = {"level": "extreme", "name": "Extreme", "feels": 47, "windows": [], "source": "Open-Meteo",
         "time": NOW, "label": "estimated"}  # fmt: skip
    assert "108" in messages.heat_alert(d, h, "mr", "u")


# ------------------------------------------------------------------ senders


def test_twilio_whatsapp_request(configured):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = dict(httpx.QueryParams(request.content.decode()))
        return httpx.Response(201, json={"sid": "SM1"})

    Sender(httpx.Client(transport=httpx.MockTransport(handler))).send(
        "whatsapp", "+919876543210", "hello"
    )
    assert seen["url"] == "https://api.twilio.com/2010-04-01/Accounts/ACtest/Messages.json"
    assert seen["auth"].startswith("Basic ")
    assert seen["body"] == {
        "To": "whatsapp:+919876543210",
        "From": "whatsapp:+14155238886",
        "Body": "hello",
    }


def test_twilio_errors_do_not_leak_secrets(configured):
    http = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(400, json={"code": 21608}))
    )
    with pytest.raises(SendError) as e:
        Sender(http).send("sms", "+919876543210", "hi")
    assert "21608" in str(e.value) and "tok" not in str(e.value)


def test_smtp_uses_starttls_and_login(configured, monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port))

        def starttls(self, context):
            calls.append(("starttls",))

        def login(self, user, pw):
            calls.append(("login", user))

        def send_message(self, m):
            calls.append(("send", m["To"], m["Subject"], m.get_content().strip()))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(channels.smtplib, "SMTP", FakeSMTP)
    Sender().send("email", "p@example.com", "body text", "Subj")
    assert calls == [
        ("connect", "smtp.test", 587),
        ("starttls",),
        ("login", "user"),
        ("send", "p@example.com", "Subj", "body text"),
    ]


def test_unconfigured_channel_refuses():
    with pytest.raises(SendError):
        Sender().send("email", "p@example.com", "x")


# ------------------------------------------------------------------ API flow


def _code(sender: FakeSender) -> str:
    return re.search(r"\b(\d{6})\b", sender.sent[-1][2]).group(1)


def test_signup_verify_and_unsubscribe(client, fake, configured, db_engine):
    r = client.post(
        "/api/v1/alerts/subscribe",
        json={"channel": "whatsapp", "address": "98765 43210", "place": "delhi", "language": "hi"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "code_sent" and body["sent_to"] == "+91******3210"
    assert fake.sent[-1][1] == "+919876543210" and "वायुकवच" in fake.sent[-1][2]
    code = _code(fake)

    # asking again within a minute is refused
    again = client.post(
        "/api/v1/alerts/subscribe",
        json={"channel": "whatsapp", "address": "+919876543210", "place": "delhi"},
    )
    assert again.status_code == 400 and again.json()["detail"]["code"] == "too_soon"

    wrong = "000000" if code != "000000" else "111111"
    bad = client.post("/api/v1/alerts/verify", json={"id": body["id"], "code": wrong})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "wrong_code"
    ok = client.post("/api/v1/alerts/verify", json={"id": body["id"], "code": code})
    assert ok.status_code == 200 and ok.json()["place"] == "Delhi"

    dup = client.post(
        "/api/v1/alerts/subscribe",
        json={"channel": "whatsapp", "address": "9876543210", "place": "delhi"},
    )
    assert dup.json()["status"] == "already_subscribed"

    with Session(db_engine) as s:
        sub = s.get(AlertSubscription, body["id"])
        assert sub.verified and sub.code_hash is None and code not in (sub.token or "")
        token = sub.token
        assert not s.execute(text("SELECT 1 FROM alert_log WHERE error LIKE '%9876%'")).first()
    page = client.get(f"/api/v1/alerts/unsubscribe?t={token}")
    assert page.status_code == 200 and "will not get" in page.text
    assert "already used" in client.get(f"/api/v1/alerts/unsubscribe?t={token}").text


def test_code_locks_after_five_wrong_tries(client, fake, configured):
    sub = client.post(
        "/api/v1/alerts/subscribe",
        json={"channel": "email", "address": "p@example.com", "place": "delhi"},
    ).json()
    code = _code(fake)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        client.post("/api/v1/alerts/verify", json={"id": sub["id"], "code": wrong})
    r = client.post("/api/v1/alerts/verify", json={"id": sub["id"], "code": code})
    assert r.json()["detail"]["code"] == "locked"


def test_signup_errors(client, fake, configured, monkeypatch):
    post = lambda **kw: client.post(  # noqa: E731
        "/api/v1/alerts/subscribe",
        json={"channel": "sms", "address": "9876543210", "place": "delhi", **kw},
    )
    assert post(address="123").json()["detail"]["code"] == "bad_address"
    assert post(daily=False, instant=False).json()["detail"]["code"] == "nothing_selected"
    assert post(place="atlantis").status_code == 404
    monkeypatch.setenv("TWILIO_SMS_FROM", "")
    get_settings.cache_clear()
    r = post()
    assert r.status_code == 503 and r.json()["detail"]["code"] == "channel_unavailable"


def test_signup_rate_limit(client, fake, configured):
    codes = [
        client.post(
            "/api/v1/alerts/subscribe",
            json={"channel": "email", "address": f"p{i}@example.com", "place": "delhi"},
        ).status_code
        for i in range(7)
    ]
    assert codes[:5] == [200] * 5 and 429 in codes[5:]


def test_channels_and_preview(client, configured):
    ch = client.get("/api/v1/alerts/channels").json()
    assert ch["email"] and ch["sms"] and ch["whatsapp"] and ch["whatsapp_number"] == "+14155238886"
    p = client.get("/api/v1/alerts/preview?place=delhi&language=mr").json()
    assert "वायुकवच" in p["text"]


# ------------------------------------------------------------------ hourly run


def _verified(s: Session, **kw) -> AlertSubscription:
    delhi = s.execute(select(District).where(District.slug == "delhi")).scalar_one()
    sub = AlertSubscription(
        channel=kw.get("channel", "sms"), address=kw.get("address", "+919876543210"),
        district_id=delhi.id, language="en", daily=kw.get("daily", True),
        instant=kw.get("instant", True), verified=True, token=kw.get("token", "t" * 43),
        created_at=NOW,
    )  # fmt: skip
    s.add(sub)
    s.commit()
    return sub


def _at(hour: int, minute: int = 5):
    return day_bounds(DAY)[0] + timedelta(hours=hour, minutes=minute)


def test_run_sends_daily_once_in_the_morning_window(session, configured):
    sub = _verified(session, instant=False)
    sender = FakeSender()
    assert service.run(session, sender, _at(6)).sent["daily"] == 0  # before 7 AM
    r = service.run(session, sender, _at(7))
    assert r.sent["daily"] == 1 and "Stop alerts: https://api.vayukavach.test" in sender.sent[0][2]
    assert service.run(session, sender, _at(8)).sent["daily"] == 0  # once a day
    session.refresh(sub)
    assert sub.last_daily_on == DAY
    sub.last_daily_on = None
    session.commit()
    assert service.run(session, sender, _at(12)).sent["daily"] == 0  # too late for "morning"


def test_run_instant_alerts_follow_levels_and_quiet_hours(session, configured, monkeypatch):
    _verified(session, daily=False)
    levels = {"aqi": "verypoor", "heat": "normal"}
    air = lambda s, d, now: {"aqi": 330, "key": levels["aqi"], "category": levels["aqi"],  # noqa: E731
                             "main": "pm25", "source": "CPCB via data.gov.in", "time": now,
                             "label": "measured"}  # fmt: skip
    heat = lambda s, d, now: {"level": levels["heat"], "name": levels["heat"].title(),  # noqa: E731
                              "feels": 44, "windows": [], "source": "Open-Meteo", "time": now,
                              "label": "estimated"}  # fmt: skip
    monkeypatch.setattr(messages, "air_facts", air)
    monkeypatch.setattr(messages, "heat_facts", heat)
    sender = FakeSender()

    assert service.run(session, sender, _at(23)).sent["aqi"] == 0  # quiet hours
    assert service.run(session, sender, _at(13)).sent["aqi"] == 1
    assert service.run(session, sender, _at(14)).sent["aqi"] == 0  # no repeat
    levels["aqi"] = "poor"
    assert service.run(session, sender, _at(15)).sent["aqi"] == 0
    levels["aqi"] = "verypoor"
    assert service.run(session, sender, _at(16)).sent["aqi"] == 0  # not re-armed by Poor
    levels["heat"] = "danger"
    assert service.run(session, sender, _at(17)).sent == {"daily": 0, "aqi": 0, "heat": 1}


def test_failed_sends_are_logged_and_retried(session, configured, monkeypatch):
    _verified(session, daily=False)
    monkeypatch.setattr(messages, "heat_facts", lambda s, d, now: None)
    monkeypatch.setattr(messages, "air_facts", lambda s, d, now: {
        "aqi": 420, "key": "severe", "category": "Severe", "main": None,
        "source": "CPCB via data.gov.in", "time": now, "label": "measured"})  # fmt: skip
    r = service.run(session, FakeSender(fail=True), _at(13))
    assert r.failed == 1
    log = session.execute(select(AlertLog).where(AlertLog.kind == "aqi")).scalar_one()
    assert not log.ok and "63015" in log.error
    assert service.run(session, FakeSender(), _at(14)).sent["aqi"] == 1  # retried next hour


def test_admin_hears_once_when_a_collector_fails_twice(session, configured, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    get_settings.cache_clear()
    now = _at(13)
    for i, status in enumerate(["ok", "failed", "failed"]):
        session.add(FetchLog(source="cpcb", status=status, started_at=now - timedelta(hours=3 - i),
                             detail="HTTP 503" if status == "failed" else None))  # fmt: skip
    session.add(FetchLog(source="weather", status="failed", started_at=now - timedelta(hours=1)))
    session.commit()
    sender = FakeSender()
    assert service.collector_failures(session, sender, now) == ["cpcb"]
    assert sender.sent[0][1] == "admin@example.com" and "HTTP 503" in sender.sent[0][2]
    assert service.collector_failures(session, sender, now + timedelta(hours=1)) == []
    session.add(FetchLog(source="cpcb", status="ok", started_at=now + timedelta(minutes=30)))
    session.commit()
    assert service.collector_failures(session, sender, now + timedelta(hours=2)) == []


def test_rate_limit_key_ignores_forged_forwarded_for():
    from starlette.requests import Request

    from app.api.limits import client_key

    def req(xff: str | None):
        headers = [(b"x-forwarded-for", xff.encode())] if xff else []
        return Request({"type": "http", "headers": headers, "client": ("10.0.0.9", 1)})

    assert client_key(req("1.2.3.4, 203.0.113.7")) == "203.0.113.7"  # added by the proxy
    assert client_key(req(None)) == "10.0.0.9"


def test_operator_notice_goes_to_admin_targets(configured, monkeypatch):
    from app.alerts.notify import notify

    monkeypatch.setenv("ADMIN_EMAIL", "ops@example.com")
    monkeypatch.setenv("ADMIN_PHONE", "98765 43210")
    get_settings.cache_clear()
    sender = FakeSender()
    assert notify("API down", sender) == 2
    assert {(c, to) for c, to, *_ in sender.sent} == {
        ("email", "ops@example.com"),
        ("whatsapp", "+919876543210"),
    }
