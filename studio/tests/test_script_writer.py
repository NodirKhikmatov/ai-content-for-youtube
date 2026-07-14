"""Script Writer agent test — mocks the LLM so this runs without
ANTHROPIC_API_KEY. Covers: an on-target script (one call), a too-short
script (triggers exactly one expand retry), and a missing beat sheet
(raises before ever calling the LLM).
"""

from uuid import uuid4

import pytest

from studio import db
from studio.agents import script_writer
from studio.agents.script_writer import Script
from studio.pacing import words_for_seconds


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
    beat_sheet = {
        "beats": [
            {"name": "hook", "content": "hook"},
            {"name": "stakes", "content": "stakes"},
            {"name": "escalation", "content": "escalation"},
            {"name": "turning_point", "content": "turning point"},
            {"name": "verdict", "content": "verdict"},
            {"name": "aftermath", "content": "aftermath"},
        ]
    }
    return {"case_id": str(case["id"]), "video_id": str(video_id), "beat_sheet": beat_sheet}


def _narration(word_count: int) -> str:
    return " ".join(["word"] * word_count)


def _mock_llm(monkeypatch, responses: list[Script]):
    call_count = {"n": 0}
    responses_iter = iter(responses)

    class FakeStructuredLLM:
        def invoke(self, _prompt):
            call_count["n"] += 1
            return next(responses_iter)

    class FakeLLM:
        def with_structured_output(self, _schema):
            return FakeStructuredLLM()

    monkeypatch.setattr(script_writer.settings, "anthropic_api_key", "fake-key-for-test")
    monkeypatch.setattr(script_writer, "ChatAnthropic", lambda **_: FakeLLM())
    return call_count


def test_on_target_script_no_retry(monkeypatch, seeded_video):
    on_target_words = words_for_seconds(10 * 60)  # 10 min, inside the 8-15 target
    call_count = _mock_llm(monkeypatch, [Script(narration=_narration(on_target_words))])

    result = script_writer.run(dict(seeded_video))

    assert call_count["n"] == 1
    assert result["script"] is not None
    video = db.get_video(seeded_video["video_id"])
    assert video["status"] == "scripted"
    assert video["script"] == result["script"]


def test_too_short_script_triggers_one_retry(monkeypatch, seeded_video):
    too_short = words_for_seconds(3 * 60)  # 3 min, well under the 8 min floor
    on_target = words_for_seconds(10 * 60)
    call_count = _mock_llm(
        monkeypatch, [Script(narration=_narration(too_short)), Script(narration=_narration(on_target))]
    )

    result = script_writer.run(dict(seeded_video))

    assert call_count["n"] == 2
    assert len(result["script"].split()) == on_target


def test_missing_beat_sheet_raises_without_calling_llm(monkeypatch, seeded_video):
    monkeypatch.setattr(script_writer.settings, "anthropic_api_key", "fake-key-for-test")
    monkeypatch.setattr(
        script_writer,
        "ChatAnthropic",
        lambda **_: (_ for _ in ()).throw(AssertionError("should not be called")),
    )

    state = dict(seeded_video)
    del state["beat_sheet"]

    with pytest.raises(RuntimeError, match="beat sheet"):
        script_writer.run(state)
