from datetime import datetime
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.alerts import messages
from app.alerts.channels import Sender, available, mask
from app.alerts.service import AlertError, subscribe, unsubscribe, verify
from app.api.common import get_district, get_http, get_now, get_session
from app.api.limits import Bucket, client_key
from app.config import get_settings
from app.models import District

router = APIRouter(prefix="/alerts", tags=["alerts"])

# every sign-up sends a message that costs money (SMS) or reputation (email): keep it slow
signup_limiter = Bucket(5, 3600)
verify_limiter = Bucket(20, 3600)

Channel = str  # email | sms | whatsapp
Lang = str  # en | hi | mr


def get_sender(http=Depends(get_http)) -> Sender:
    return Sender(http)


def _error(e: AlertError, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": e.code, "message": str(e)})


class Channels(BaseModel):
    email: bool
    sms: bool
    whatsapp: bool
    whatsapp_join: str | None = Field(
        description="Twilio sandbox: send this text to the sandbox number first"
    )
    whatsapp_number: str | None


@router.get("/channels", response_model=Channels)
def channels():
    """Which alert channels are set up on this server."""
    s = get_settings()
    sandbox = s.twilio_whatsapp_from.removeprefix("whatsapp:") or None
    return {
        **available(),
        "whatsapp_join": s.twilio_whatsapp_join or None,
        "whatsapp_number": sandbox,
    }


class SubscribeIn(BaseModel):
    channel: str = Field(pattern="^(email|sms|whatsapp)$")
    address: str = Field(min_length=3, max_length=254)
    place: str = Field(min_length=2, max_length=60)
    language: str = Field(default="en", pattern="^(en|hi|mr)$")
    daily: bool = True
    instant: bool = True


class SubscribeOut(BaseModel):
    id: int
    status: str  # code_sent | already_subscribed
    sent_to: str


@router.post("/subscribe", response_model=SubscribeOut)
def subscribe_(
    body: SubscribeIn,
    request: Request,
    session: Session = Depends(get_session),
    sender: Sender = Depends(get_sender),
    now: datetime = Depends(get_now),
):
    """Start a sign-up: sends a 6-digit code to the address. Nothing is sent until it is
    confirmed with /alerts/verify."""
    if not signup_limiter.allow(client_key(request)):
        raise HTTPException(status_code=429, detail="Too many sign-ups. Try again later.")
    district = get_district(body.place, session)
    try:
        sub, status = subscribe(
            session,
            sender,
            channel=body.channel,
            address=body.address,
            district=district,
            language=body.language,
            daily=body.daily,
            instant=body.instant,
            now=now,
        )
    except AlertError as e:
        raise _error(e, 503 if e.code in ("channel_unavailable", "send_failed") else 400) from None
    return {"id": sub.id, "status": status, "sent_to": mask(sub.channel, sub.address)}


class VerifyIn(BaseModel):
    id: int
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class VerifyOut(BaseModel):
    verified: bool
    channel: str
    sent_to: str
    place: str
    daily: bool
    instant: bool


@router.post("/verify", response_model=VerifyOut)
def verify_(
    body: VerifyIn,
    request: Request,
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    if not verify_limiter.allow(client_key(request)):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    try:
        sub = verify(session, body.id, body.code, now)
    except AlertError as e:
        raise _error(e) from None
    return {
        "verified": True,
        "channel": sub.channel,
        "sent_to": mask(sub.channel, sub.address),
        "place": session.get(District, sub.district_id).name,
        "daily": sub.daily,
        "instant": sub.instant,
    }


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_(
    t: str = Query(min_length=20, max_length=64), session: Session = Depends(get_session)
):
    """One-click stop link sent in every alert."""
    done = unsubscribe(session, t)
    text = (
        "You will not get VayuKavach alerts on this address any more."
        if done
        else "This link was already used or is not valid. No alerts are linked to it."
    )
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
        "<title>VayuKavach alerts</title><body style='font-family:system-ui;max-width:32rem;"
        "margin:3rem auto;padding:0 1rem;color:#17212b'><h1>Alerts stopped</h1>"
        f"<p>{escape(text)}</p>"
        f"<p><a href='{escape(get_settings().frontend_origin)}'>Open VayuKavach</a></p></body>"
    )


class Preview(BaseModel):
    text: str
    note: str = "Example of today's 7 AM summary, built from the latest data."


@router.get("/preview", response_model=Preview)
def preview(
    place: str = Query(min_length=2, max_length=60),
    language: str = Query(default="en", pattern="^(en|hi|mr)$"),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
):
    district = get_district(place, session)
    return {"text": messages.daily(session, district, language, now, "(your stop link)")}
