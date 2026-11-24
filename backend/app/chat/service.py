"""Ask VayuKavach: scope check -> engine (Gemini / Ollama / rules) -> guard -> sources -> log."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.chat import llm, rules
from app.chat.scope import REFUSAL, detect_language, in_scope
from app.chat.tools import ToolContext
from app.config import get_settings
from app.models import ChatLog

log = logging.getLogger("vayukavach.chat")
MAX_LEN = 500
NO_DATA = {
    "en": "Sorry, I don't have data to answer that.",
    "hi": "माफ़ कीजिए, इसका जवाब देने के लिए मेरे पास डेटा नहीं है।",
    "mr": "माफ करा, याचे उत्तर देण्यासाठी माझ्याकडे डेटा नाही.",
}


@dataclass
class Reply:
    answer: str
    sources: list[dict]
    refused: bool
    language: str
    engine: str


def engine_name() -> str:
    s = get_settings()
    if s.gemini_api_key:
        return "gemini"
    if s.ollama_model:
        return "ollama"
    return "rules"


def redact(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[email]", text)
    return re.sub(r"\+?\d[\d\s-]{6,}\d", "[number]", text)[:MAX_LEN]


def sources_of(ctx: ToolContext) -> list[dict]:
    seen, out = set(), []
    for c in ctx.calls:
        if not c.get("available") or not c.get("source"):
            continue
        key = (c["source"], c.get("time"), c.get("label"))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "source": c["source"],
                "time": c.get("time"),
                "label": c.get("label"),
                "tool": c.get("tool"),
            }
        )
    return out


def respond(
    session: Session,
    http: httpx.Client | None,
    now: datetime,
    message: str,
    place: str | None = None,
    language: str | None = None,
) -> Reply:
    message = (message or "").strip()[:MAX_LEN]
    lang = detect_language(message, language if language in REFUSAL else None)
    if not message or not in_scope(message):
        reply = Reply(REFUSAL[lang], [], True, lang, "scope")
        _log(session, message, reply, [])
        return reply
    ctx = ToolContext(session=session, now=now, http=http)
    engine = engine_name()
    try:
        if engine == "gemini" and http is not None:
            text = llm.gemini_answer(ctx, http, message, place, lang)
        elif engine == "ollama" and http is not None:
            text = llm.ollama_answer(ctx, http, message, place, lang)
        else:
            engine, text = "rules", rules.answer(ctx, message, place, lang)
    except (llm.EngineError, httpx.HTTPError) as exc:
        log.warning("%s failed (%s); falling back to rules", engine, exc)
        ctx.calls.clear()
        engine, text = "rules", rules.answer(ctx, message, place, lang)
    sources = sources_of(ctx)
    # Guard: a number with no data behind it is a guess. Replace the answer.
    if not sources and re.search(r"\d", text):
        text = NO_DATA[lang]
    if not text:
        text = NO_DATA[lang]
    reply = Reply(text, sources, False, lang, engine)
    _log(session, message, reply, [c.get("tool") for c in ctx.calls])
    return reply


def _log(session: Session, message: str, reply: Reply, tools: list) -> None:
    try:
        session.add(
            ChatLog(
                created_at=datetime.now(UTC),
                question=redact(message),
                language=reply.language,
                refused=reply.refused,
                engine=reply.engine,
                tools=tools,
                had_sources=bool(reply.sources),
            )
        )
        session.commit()
    except Exception:  # noqa: BLE001 - logging must never break an answer
        session.rollback()
        log.exception("chat log failed")
