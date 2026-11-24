from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.common import get_http, get_now, get_session
from app.api.limits import Bucket, client_key
from app.chat.service import respond

router = APIRouter(tags=["chat"])

PER_MINUTE = 10  # per client: LLM calls are the scarce resource
limiter = Bucket(PER_MINUTE, 60)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    place: str | None = Field(default=None, max_length=60)
    language: str | None = Field(default=None, description="en | hi | mr (default: detect)")


class Source(BaseModel):
    source: str
    time: str | None
    label: str | None
    tool: str | None


class ChatOut(BaseModel):
    answer: str
    sources: list[Source]
    refused: bool
    language: str
    engine: str  # gemini | ollama | rules | scope


@router.post("/chat", response_model=ChatOut)
def chat(
    body: ChatIn,
    request: Request,
    session: Session = Depends(get_session),
    http: httpx.Client = Depends(get_http),
    now: datetime = Depends(get_now),
):
    """Ask VayuKavach. Answers only from VayuKavach's data, with sources; refuses anything
    outside air quality, heat and the app."""
    if not limiter.allow(client_key(request)):
        raise HTTPException(status_code=429, detail="Too many questions. Please wait a minute.")
    r = respond(session, http, now, body.message, body.place, body.language)
    return {
        "answer": r.answer,
        "sources": r.sources,
        "refused": r.refused,
        "language": r.language,
        "engine": r.engine,
    }
