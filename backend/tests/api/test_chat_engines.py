import json

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import chat as chat_api
from app.chat import service
from app.config import get_settings
from app.models import ChatLog
from tests.api.conftest import NOW


@pytest.fixture
def session(seeded, db_engine):
    with Session(db_engine) as s:
        yield s


def gemini_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "TEST-GEMINI-KEY")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_settings():
    yield
    get_settings.cache_clear()


def test_gemini_calls_tools_and_keeps_the_key_out_of_the_url(session, monkeypatch):
    gemini_env(monkeypatch)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append((str(request.url), request.headers.get("x-goog-api-key"), body))
        if len(seen) == 1:
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [
                                    {
                                        "functionCall": {
                                            "name": "get_aqi",
                                            "args": {"place": "delhi"},
                                        }
                                    }
                                ],
                            }
                        }
                    ]
                },
            )
        result = body["contents"][-1]["parts"][0]["functionResponse"]["response"]["result"]
        text = f"Delhi's AQI is {result['aqi']} ({result['category']}), from {result['source']}."
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    r = service.respond(session, http, NOW, "What is the AQI in Delhi?", "delhi")
    assert r.engine == "gemini" and not r.refused
    assert "310" in r.answer and r.sources and r.sources[0]["label"] == "measured"
    assert all("TEST-GEMINI-KEY" not in url for url, _, _ in seen)
    assert all(key == "TEST-GEMINI-KEY" for _, key, _ in seen)
    prompt = " ".join(seen[0][2]["systemInstruction"]["parts"][0]["text"].split())
    assert "Never guess a number" in prompt and "2026-11-08" in prompt  # IST date


def test_number_without_data_is_replaced(session, monkeypatch):
    gemini_env(monkeypatch)
    invented = {"candidates": [{"content": {"parts": [{"text": "Delhi's AQI is 42."}]}}]}
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=invented)))
    r = service.respond(session, http, NOW, "What is the AQI in Delhi?", "delhi")
    assert "42" not in r.answer and r.sources == []
    assert "don't have data" in r.answer


def test_gemini_failure_falls_back_to_rules(session, monkeypatch):
    gemini_env(monkeypatch)
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    r = service.respond(session, http, NOW, "What is the AQI in Delhi?", "delhi")
    assert r.engine == "rules" and r.sources and "310" in r.answer


def test_out_of_scope_never_reaches_the_model(session, monkeypatch):
    gemini_env(monkeypatch)
    calls = []
    http = httpx.Client(
        transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(500))
    )
    r = service.respond(session, http, NOW, "Who will win the cricket match?", "delhi")
    assert r.refused and calls == []


def test_ollama_tool_loop(session, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "gemma3")
    get_settings.cache_clear()
    steps = []

    def handler(request: httpx.Request) -> httpx.Response:
        steps.append(json.loads(request.content))
        if len(steps) == 1:
            return httpx.Response(
                200,
                json={
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {"function": {"name": "get_heat_risk", "arguments": {"place": "delhi"}}}
                        ],
                    }
                },
            )
        tool = json.loads(steps[-1]["messages"][-1]["content"])
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": f"Heat level in Delhi: {tool['level']} (Open-Meteo, estimated).",
                }
            },
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    r = service.respond(session, http, NOW, "What is the heat risk in Delhi?", "delhi")
    assert r.engine == "ollama" and "Heat level in Delhi" in r.answer
    assert r.sources[0]["label"] == "estimated"
    assert steps[0]["model"] == "gemma3" and steps[0]["tools"]


def test_unknown_tool_and_bad_args_are_data_not_errors(session):
    from app.chat.tools import ToolContext, call

    ctx = ToolContext(session=session, now=NOW)
    assert call(ctx, "delete_database", {})["available"] is False
    assert call(ctx, "get_aqi", {"nonsense": 1})["available"] is False


def test_chat_endpoint_logs_redacted_questions_and_rate_limits(client, db_engine, monkeypatch):
    monkeypatch.setattr(service, "engine_name", lambda: "rules")
    chat_api.limiter.clear()
    body = client.post(
        "/api/v1/chat",
        json={"message": "AQI in Delhi? mail me at a.b@x.com or +91 98765 43210", "place": "delhi"},
    ).json()
    assert body["engine"] == "rules" and body["sources"] and body["language"] == "en"
    with Session(db_engine) as s:
        q = s.execute(select(ChatLog.question).order_by(ChatLog.id.desc())).scalars().first()
    assert "a.b@x.com" not in q and "98765" not in q and "[email]" in q and "[number]" in q
    codes = [
        client.post("/api/v1/chat", json={"message": "AQI in Delhi?"}).status_code
        for _ in range(12)
    ]
    assert 429 in codes
    chat_api.limiter.clear()


def test_forecast_days_are_labelled_relative_to_today(session):
    from app.chat.tools import ToolContext, call

    r = call(ToolContext(session=session, now=NOW), "get_forecast", {"place": "delhi", "days": 3})
    if r["available"] and r["heat"]:
        assert r["heat"][0]["day"] == "today" and r["today"] == "2026-11-08"
        assert [h["day"] for h in r["heat"][:2]] == ["today", "tomorrow"]


def test_forecast_always_includes_tomorrow(session):
    from app.chat.tools import ToolContext, call

    r = call(ToolContext(session=session, now=NOW), "get_forecast", {"place": "delhi", "days": 1})
    assert r["available"]
    series = r["heat"] or r["aqi"]
    assert [x["day"] for x in series[:2]] == ["today", "tomorrow"]
