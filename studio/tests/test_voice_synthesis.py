"""Voice Synthesis agent test — mocks ElevenLabsBackend so this runs
without ELEVENLABS_API_KEY. Covers a successful synthesis (writes a local
file, updates the DB) and confirms R2 upload failure degrades gracefully
rather than failing the agent (no R2 credentials in this project's .env).
"""

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from studio import db
from studio.agents import voice_synthesis


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
    yield {"case_id": str(case["id"]), "video_id": str(video_id), "script": "This is a test script."}
    shutil.rmtree(voice_synthesis.MEDIA_DIR / str(video_id), ignore_errors=True)


class _FakeBackend:
    def synthesize(self, text: str, voice_id: str) -> bytes:
        return b"fake mp3 bytes"


def test_synthesizes_and_writes_local_file(monkeypatch, seeded_video):
    monkeypatch.setattr(voice_synthesis, "ElevenLabsBackend", lambda: _FakeBackend())
    # no R2 credentials configured in this project's .env — confirm that's
    # not fatal, not just assumed.
    monkeypatch.setattr(
        voice_synthesis.storage,
        "upload_file",
        lambda *_: (_ for _ in ()).throw(RuntimeError("R2 credentials missing")),
    )

    result = voice_synthesis.run(dict(seeded_video))

    local_path = Path(result["voice_audio_path"])
    assert local_path.exists()
    assert local_path.read_bytes() == b"fake mp3 bytes"

    video = db.get_video(seeded_video["video_id"])
    assert video["voice_audio_path"] == str(local_path)


def test_missing_script_raises_without_calling_backend(monkeypatch, seeded_video):
    monkeypatch.setattr(
        voice_synthesis,
        "ElevenLabsBackend",
        lambda: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    state = dict(seeded_video)
    del state["script"]

    with pytest.raises(RuntimeError, match="script"):
        voice_synthesis.run(state)
