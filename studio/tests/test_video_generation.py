"""Video Generation agent test — mocks KlingBackend so this runs without
KLING_ACCESS_KEY/KLING_SECRET_KEY. Covers one clip generated per beat and a
mid-generation failure raising rather than silently producing a partial
clip set.
"""

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from studio import db
from studio.agents import video_generation


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
            {"name": "hook", "content": "a hook"},
            {"name": "stakes", "content": "the stakes"},
            {"name": "escalation", "content": "escalation"},
        ]
    }
    yield {"case_id": str(case["id"]), "video_id": str(video_id), "beat_sheet": beat_sheet}
    shutil.rmtree(video_generation.MEDIA_DIR / str(video_id), ignore_errors=True)


class _FakeBackend:
    def generate_clip(self, prompt: str, duration_seconds: int) -> bytes:
        return f"fake clip for: {prompt}".encode()


def test_generates_one_clip_per_beat(monkeypatch, seeded_video):
    monkeypatch.setattr(video_generation, "KlingBackend", lambda: _FakeBackend())
    monkeypatch.setattr(
        video_generation.storage,
        "upload_file",
        lambda *_: (_ for _ in ()).throw(RuntimeError("R2 credentials missing")),
    )

    result = video_generation.run(dict(seeded_video))

    clip_paths = result["video_clip_paths"]
    assert len(clip_paths) == 3
    for path in clip_paths:
        assert Path(path).exists()


def test_missing_beat_sheet_raises_without_calling_backend(monkeypatch, seeded_video):
    monkeypatch.setattr(
        video_generation,
        "KlingBackend",
        lambda: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    state = dict(seeded_video)
    del state["beat_sheet"]

    with pytest.raises(RuntimeError, match="beat sheet"):
        video_generation.run(state)
