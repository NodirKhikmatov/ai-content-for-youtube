"""Storytelling agent test — mocks the LLM so this runs without
ANTHROPIC_API_KEY. Covers: a compliant beat sheet (one call), a hook that's
too long (triggers exactly one retry), and a beat sheet missing a required
beat (raises rather than silently proceeding).
"""

from uuid import uuid4

import pytest

from studio import db
from studio.agents import storytelling
from studio.agents.storytelling import Beat, BeatSheet


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


def _all_beats(hook_word_count: int) -> list[Beat]:
    hook_text = " ".join(["word"] * hook_word_count)
    return [
        Beat(name="hook", content=hook_text),
        Beat(name="stakes", content="stakes content"),
        Beat(name="escalation", content="escalation content"),
        Beat(name="turning_point", content="turning point content"),
        Beat(name="verdict", content="verdict content"),
        Beat(name="aftermath", content="aftermath content"),
    ]


def _mock_llm(monkeypatch, responses: list[BeatSheet]):
    call_count = {"n": 0}
    responses_iter = iter(responses)

    class FakeStructuredLLM:
        def invoke(self, _prompt):
            call_count["n"] += 1
            return next(responses_iter)

    class FakeLLM:
        def with_structured_output(self, _schema):
            return FakeStructuredLLM()

    monkeypatch.setattr(storytelling.settings, "anthropic_api_key", "fake-key-for-test")
    monkeypatch.setattr(storytelling, "ChatAnthropic", lambda **_: FakeLLM())
    return call_count


def test_short_hook_no_retry(monkeypatch, seeded_video):
    call_count = _mock_llm(monkeypatch, [BeatSheet(beats=_all_beats(hook_word_count=10))])

    result = storytelling.run(dict(seeded_video))

    assert call_count["n"] == 1
    beat_sheet = result["beat_sheet"]
    assert len(beat_sheet["beats"]) == 6
    assert beat_sheet["hook_within_budget"] is True


def test_long_hook_triggers_one_retry(monkeypatch, seeded_video):
    call_count = _mock_llm(
        monkeypatch,
        [
            BeatSheet(beats=_all_beats(hook_word_count=40)),  # ~16s, over 8s budget
            BeatSheet(beats=_all_beats(hook_word_count=8)),  # ~3.2s, within budget
        ],
    )

    result = storytelling.run(dict(seeded_video))

    assert call_count["n"] == 2
    assert result["beat_sheet"]["hook_within_budget"] is True


def test_missing_beat_raises(monkeypatch, seeded_video):
    incomplete = [b for b in _all_beats(hook_word_count=10) if b.name != "aftermath"]
    _mock_llm(monkeypatch, [BeatSheet(beats=incomplete)])

    with pytest.raises(RuntimeError, match="missing"):
        storytelling.run(dict(seeded_video))
