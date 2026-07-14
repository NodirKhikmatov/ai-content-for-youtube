"""Subtitle agent test — mocks Deepgram (no DEEPGRAM_API_KEY) but uses real
ffmpeg for audio extraction and caption burn-in against a synthetic clip
(see conftest.py). Covers the low-WER path (captions burned in) and the
high-WER path (burn-in skipped, un-captioned cut kept) — the actual
decision graph.py-adjacent agents rely on downstream, not just the pass
case. word_error_rate and words_to_srt are also unit-tested directly, no
mocking needed for pure functions.
"""

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from studio import db
from studio.agents import subtitle
from studio.agents.subtitle import word_error_rate, words_to_srt
from studio.tools.ffmpeg_utils import probe_duration_seconds


def test_word_error_rate_identical_text_is_zero():
    assert word_error_rate("the quick brown fox", "the quick brown fox") == 0.0


def test_word_error_rate_totally_different_is_one():
    assert word_error_rate("alpha beta gamma", "delta epsilon zeta") == pytest.approx(1.0)


def test_word_error_rate_partial_mismatch():
    # 1 wrong word out of 4 reference words
    assert word_error_rate("the quick brown fox", "the slow brown fox") == pytest.approx(0.25)


def test_word_error_rate_empty_reference_and_hypothesis():
    assert word_error_rate("", "") == 0.0
    assert word_error_rate("", "something") == 1.0


def test_words_to_srt_empty_list():
    assert words_to_srt([]) == ""


def test_words_to_srt_produces_sequential_numbered_blocks():
    words = [
        {"word": "hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.5, "end": 1.0},
    ]
    srt = words_to_srt(words)
    assert srt.startswith("1\n00:00:00,000 --> 00:00:01,000\nhello world")


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
    yield {
        "case_id": str(case["id"]),
        "video_id": str(video_id),
        "script": "the quick brown fox jumps over the lazy dog",
    }
    shutil.rmtree(subtitle.MEDIA_DIR / str(video_id), ignore_errors=True)


def _fake_transcript(words: list[dict]) -> dict:
    return {"transcript": " ".join(w["word"] for w in words), "words": words}


def test_low_wer_burns_in_captions(monkeypatch, seeded_video, synthetic_clip_factory):
    clip = synthetic_clip_factory("assembled.mp4", duration=3.0)
    matching_words = [
        {"word": w, "start": i * 0.3, "end": i * 0.3 + 0.25}
        for i, w in enumerate(seeded_video["script"].split())
    ]
    monkeypatch.setattr(
        subtitle, "transcribe", lambda _audio_bytes: _fake_transcript(matching_words)
    )
    monkeypatch.setattr(
        subtitle.storage,
        "upload_file",
        lambda *_: (_ for _ in ()).throw(RuntimeError("R2 credentials missing")),
    )

    state = dict(seeded_video)
    state["assembled_video_path"] = str(clip)

    result = subtitle.run(state)

    assert result["assembled_video_path"] != str(clip)  # burned-in file, not the original
    final_path = Path(result["assembled_video_path"])
    assert final_path.exists()
    assert probe_duration_seconds(final_path) == pytest.approx(3.0, abs=0.3)

    video = db.get_video(seeded_video["video_id"])
    assert video["status"] == "in_review"


def test_high_wer_skips_burn_in(monkeypatch, seeded_video, synthetic_clip_factory):
    clip = synthetic_clip_factory("assembled.mp4", duration=3.0)
    unrelated_words = [
        {"word": w, "start": i * 0.3, "end": i * 0.3 + 0.25}
        for i, w in enumerate(["completely", "unrelated", "transcript", "text"])
    ]
    monkeypatch.setattr(
        subtitle, "transcribe", lambda _audio_bytes: _fake_transcript(unrelated_words)
    )
    monkeypatch.setattr(
        subtitle.storage,
        "upload_file",
        lambda *_: (_ for _ in ()).throw(RuntimeError("R2 credentials missing")),
    )

    state = dict(seeded_video)
    state["assembled_video_path"] = str(clip)

    result = subtitle.run(state)

    assert result["assembled_video_path"] == str(clip)  # unchanged, no burn-in

    video = db.get_video(seeded_video["video_id"])
    assert video["status"] == "in_review"


def test_missing_script_raises_before_transcribing(monkeypatch, seeded_video, synthetic_clip_factory):
    clip = synthetic_clip_factory("assembled.mp4", duration=2.0)
    monkeypatch.setattr(
        subtitle,
        "transcribe",
        lambda *_: (_ for _ in ()).throw(AssertionError("should not be called")),
    )

    state = dict(seeded_video)
    state["assembled_video_path"] = str(clip)
    del state["script"]

    with pytest.raises(RuntimeError, match="script"):
        subtitle.run(state)
