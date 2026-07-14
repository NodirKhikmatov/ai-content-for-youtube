"""Real ffmpeg tests — no mocking. ffmpeg is a local binary with no API key
requirement, so there's no reason to fake the one dependency that's
actually free to exercise for real.
"""

import pytest

from studio.tools.ffmpeg_utils import (
    FfmpegError,
    concat_clips,
    extract_audio,
    match_video_to_audio_duration,
    mux_audio_over_video,
    probe_duration_seconds,
)


def test_probe_duration_matches_generated_length(synthetic_clip_factory):
    clip = synthetic_clip_factory("clip.mp4", duration=3.0)
    assert probe_duration_seconds(clip) == pytest.approx(3.0, abs=0.2)


def test_concat_clips_sums_durations(synthetic_clip_factory, tmp_path):
    clip_a = synthetic_clip_factory("a.mp4", duration=2.0)
    clip_b = synthetic_clip_factory("b.mp4", duration=3.0)
    out = tmp_path / "out.mp4"

    concat_clips([clip_a, clip_b], out)

    assert probe_duration_seconds(out) == pytest.approx(5.0, abs=0.3)


def test_concat_clips_rejects_empty_list(tmp_path):
    with pytest.raises(FfmpegError, match="no clips"):
        concat_clips([], tmp_path / "out.mp4")


def test_match_video_to_audio_duration_trims_when_long(synthetic_clip_factory, tmp_path):
    clip = synthetic_clip_factory("long.mp4", duration=8.0)
    out = tmp_path / "trimmed.mp4"

    match_video_to_audio_duration(clip, target_seconds=3.0, out_path=out)

    assert probe_duration_seconds(out) == pytest.approx(3.0, abs=0.3)


def test_match_video_to_audio_duration_loops_when_short(synthetic_clip_factory, tmp_path):
    clip = synthetic_clip_factory("short.mp4", duration=2.0)
    out = tmp_path / "looped.mp4"

    match_video_to_audio_duration(clip, target_seconds=7.0, out_path=out)

    assert probe_duration_seconds(out) == pytest.approx(7.0, abs=0.3)


def test_mux_audio_over_video_uses_audio_duration(
    synthetic_clip_factory, synthetic_audio_factory, tmp_path
):
    video = synthetic_clip_factory("video.mp4", duration=10.0)
    audio = synthetic_audio_factory("audio.mp3", duration=4.0)
    out = tmp_path / "muxed.mp4"

    mux_audio_over_video(video, audio, out)

    # -shortest: the muxed file is capped by whichever stream is shorter
    assert probe_duration_seconds(out) == pytest.approx(4.0, abs=0.3)


def test_extract_audio_produces_playable_audio_file(synthetic_clip_factory, tmp_path):
    clip = synthetic_clip_factory("with_audio.mp4", duration=3.0)
    out = tmp_path / "extracted.mp3"

    extract_audio(clip, out)

    assert out.exists()
    assert probe_duration_seconds(out) == pytest.approx(3.0, abs=0.3)
