"""Deep Research agent test — mocks the LLM and search calls so this runs
without ANTHROPIC_API_KEY / TAVILY_API_KEY. Verifies the two-pass
orchestration and DB writes, not research quality — there's no ground truth
to check that against in a unit test; that's what Fact Checker is for.
"""

from uuid import uuid4

import pytest

from studio import db
from studio.agents import deep_research
from studio.agents.deep_research import ResearchBrief, SourcedClaim


@pytest.fixture
def seeded_video():
    """Creates and selects its own throwaway case by title, rather than going
    through get_top_candidate_case — that returns the globally highest-scored
    *real* backlog candidate, not whatever this fixture just inserted, and an
    earlier version of this fixture silently burned through the real backlog
    because of exactly that mismatch."""
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
    return {"case_id": str(case["id"]), "video_id": str(video_id)}


def test_two_pass_orchestration(monkeypatch, seeded_video):
    monkeypatch.setattr(deep_research.settings, "anthropic_api_key", "fake-key-for-test")

    gather_brief = ResearchBrief(
        thesis="test thesis",
        turning_point="test turning point",
        claims=[SourcedClaim(claim="a claim", source_url="https://example.com", confidence="high")],
    )
    counter_brief = ResearchBrief(
        thesis="unused",
        turning_point="unused",
        counterpoints=[
            SourcedClaim(claim="a counterpoint", source_url="https://example.com/2", confidence="medium")
        ],
        open_questions=["one open question"],
    )
    responses = iter([gather_brief, counter_brief])

    class FakeStructuredLLM:
        def invoke(self, _prompt):
            return next(responses)

    class FakeLLM:
        def with_structured_output(self, _schema):
            return FakeStructuredLLM()

    monkeypatch.setattr(deep_research, "ChatAnthropic", lambda **_: FakeLLM())
    monkeypatch.setattr(
        deep_research, "tavily_search", lambda query, **_: [{"title": "t", "url": "https://example.com", "content": "c"}]
    )

    result = deep_research.run(dict(seeded_video))

    brief = result["research_brief"]
    assert brief["thesis"] == "test thesis"
    assert len(brief["claims"]) == 1
    assert len(brief["counterpoints"]) == 1
    assert "one open question" in brief["open_questions"]

    video = db.get_case(seeded_video["case_id"])  # sanity: case row still there
    assert video["status"] == "selected"
