"""Video Assembly agent test — real ffmpeg end to end against synthetic
clips/audio (see conftest.py), only R2 upload is mocked (no credentials).
This is the one Day 5 agent where the actual media pipeline, not just the
orchestration around it, gets verified.
"""

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from studio import db
from studio.agents import video_assembly
from studio.tools.ffmpeg_utils import probe_duration_seconds


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
    yield {"case_id": str(case["id"]), "video_id": str(video_id)}
    shutil.rmtree(video_assembly.MEDIA_DIR / str(video_id), ignore_errors=True)


def test_assembled_video_matches_narration_duration(
    monkeypatch, seeded_video, synthetic_clip_factory, synthetic_audio_factory, tmp_path
):
    monkeypatch.setattr(
        video_assembly.storage,
        "upload_file",
        lambda *_: (_ for _ in ()).throw(RuntimeError("R2 credentials missing")),
    )

    clip_a = synthetic_clip_factory("a.mp4", duration=2.0)
    clip_b = synthetic_clip_factory("b.mp4", duration=2.0)
    narration = synthetic_audio_factory("voice.mp3", duration=9.0)

    state = dict(seeded_video)
    state["video_clip_paths"] = [str(clip_a), str(clip_b)]
    state["voice_audio_path"] = str(narration)

    result = video_assembly.run(state)

    assembled_path = Path(result["assembled_video_path"])
    assert assembled_path.exists()
    # 2 clips totalling 4s of visuals, looped to cover the 9s narration —
    # this is the actual pacing rule (Section 4.4), not just a returned flag
    assert probe_duration_seconds(assembled_path) == pytest.approx(9.0, abs=0.5)

    video = db.get_video(seeded_video["video_id"])
    assert video["status"] == "produced"


def test_missing_clips_raises_without_running_ffmpeg(seeded_video, synthetic_audio_factory):
    narration = synthetic_audio_factory("voice.mp3", duration=5.0)
    state = dict(seeded_video)
    state["voice_audio_path"] = str(narration)
    # no video_clip_paths

    with pytest.raises(RuntimeError, match="video_clip_paths"):
        video_assembly.run(state)
