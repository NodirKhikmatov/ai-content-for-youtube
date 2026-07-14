"""Fact Checker agent test — mocks the LLM and search calls so this runs
without ANTHROPIC_API_KEY/TAVILY_API_KEY. Covers both branches that matter:
all claims verified (pipeline continues) and one disputed claim (hard stop,
video rejected) — the two outcomes graph.py's conditional edge routes on.
"""

from uuid import uuid4

import pytest

from studio import db
from studio.agents import fact_checker
from studio.agents.fact_checker import ClaimVerdict, FactCheckResult


@pytest.fixture
def seeded_video():
    channel_id = db.get_channel_id("The Turning Point")
    title = f"Test Case {uuid4()}"
    db.upsert_case(
        channel_id,
        title=title,
        jurisdiction="Nowhere",
        era="2020",
        turning_point="a test fixture",
        score=1.0,
    )
    case = db.get_case_by_title(channel_id, title)
    db.mark_case_selected(case["id"])
    video_id = db.create_video_for_case(case["id"], channel_id, case["title"])
    return {
        "case_id": str(case["id"]),
        "video_id": str(video_id),
        "research_brief": {
            "thesis": "t",
            "turning_point": "tp",
            "claims": [{"claim": "a claim", "source_url": "https://example.com", "confidence": "high"}],
        },
    }


def _mock_llm(monkeypatch, verdicts: list[ClaimVerdict]):
    class FakeStructuredLLM:
        def invoke(self, _prompt):
            return FactCheckResult(verdicts=verdicts)

    class FakeLLM:
        def with_structured_output(self, _schema):
            return FakeStructuredLLM()

    monkeypatch.setattr(fact_checker.settings, "anthropic_api_key", "fake-key-for-test")
    monkeypatch.setattr(fact_checker, "ChatAnthropic", lambda **_: FakeLLM())
    monkeypatch.setattr(
        fact_checker,
        "tavily_search",
        lambda query, **_: [{"title": "t", "url": "https://example.com", "content": "c"}],
    )


def test_all_verified_continues_pipeline(monkeypatch, seeded_video):
    _mock_llm(
        monkeypatch,
        [ClaimVerdict(claim="a claim", verdict="verified", rationale="corroborated")],
    )

    result = fact_checker.run(dict(seeded_video))

    assert result["fact_check"]["hard_stop"] is False
    video = db.get_video(seeded_video["video_id"])
    assert video["status"] == "researched"


def test_disputed_claim_hard_stops(monkeypatch, seeded_video):
    _mock_llm(
        monkeypatch,
        [ClaimVerdict(claim="a claim", verdict="disputed", rationale="sources conflict")],
    )

    result = fact_checker.run(dict(seeded_video))

    assert result["fact_check"]["hard_stop"] is True
    assert "a claim" in result["fact_check"]["hard_stop_reason"]
    video = db.get_video(seeded_video["video_id"])
    assert video["status"] == "rejected"


def test_no_claims_hard_stops_without_calling_llm(monkeypatch, seeded_video):
    monkeypatch.setattr(fact_checker.settings, "anthropic_api_key", "fake-key-for-test")

    state = dict(seeded_video)
    state["research_brief"] = {"thesis": "t", "turning_point": "tp", "claims": []}

    result = fact_checker.run(state)

    assert result["fact_check"]["hard_stop"] is True
    video = db.get_video(seeded_video["video_id"])
    assert video["status"] == "rejected"
