"""Spec Phase 11 evaluation: every in-scope answer has sources, every out-of-scope question is
refused, no-data questions say so without guessing. Runs the rule engine (no API key needed)."""

from pathlib import Path

import pytest
import yaml
from sqlalchemy.orm import Session

from app.chat import service
from tests.api.conftest import NOW

CASES = yaml.safe_load((Path(__file__).parents[1] / "chat_eval.yaml").read_text(encoding="utf-8"))


def test_eval_has_50_questions_across_categories():
    assert len(CASES) == 50
    assert len({c["id"] for c in CASES}) == 50
    kinds = {c["expect"] for c in CASES}
    assert {"answer", "no_data", "refuse"} <= kinds


@pytest.fixture
def ask(seeded, db_engine, monkeypatch):
    monkeypatch.setattr(service, "engine_name", lambda: "rules")
    with Session(db_engine) as session:
        yield lambda q, place="delhi": service.respond(session, None, NOW, q, place)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_chat_eval(ask, case):
    r = ask(case["q"], case.get("place", "delhi"))
    expect = case["expect"]
    if expect == "refuse":
        assert r.refused, r.answer
        assert r.sources == []
    elif expect == "answer":
        assert not r.refused, r.answer
        assert r.sources, f"no sources: {r.answer}"
        assert all(s["source"] for s in r.sources)
    elif expect == "no_data":
        assert not r.refused, r.answer
        assert r.sources == [], r.answer
        assert any(
            w in r.answer for w in ("not available", "उपलब्ध नहीं", "उपलब्ध नाही", "don't have")
        )
    else:  # inscope
        assert not r.refused, r.answer
    low = r.answer.lower()
    for s in case.get("must_contain", []):
        assert s.lower() in low, f"missing {s!r}: {r.answer}"
    for s in case.get("must_not_contain", []):
        assert s.lower() not in low, f"contains {s!r}: {r.answer}"
