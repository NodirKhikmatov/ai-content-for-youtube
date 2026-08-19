"""Shared fixtures for the Day 5 media agents. ffmpeg is installed locally
(unlike ElevenLabs/Kling/Deepgram, which need paid API keys this project
doesn't have), so these generate real tiny synthetic clips/audio via
ffmpeg's lavfi sources — real ffmpeg orchestration gets tested here, not
just mocked.
"""

import subprocess
from pathlib import Path

import pytest

from studio.config import settings


@pytest.fixture(autouse=True)
def _real_backends_by_default(monkeypatch):
    """Every *_BACKEND setting defaults to the real (paid) vendor, and every
    test that exercises voice/video/transcribe/quality-review mocks that
    real vendor's class/function directly (ElevenLabsBackend, KlingBackend,
    transcribe, review_video) — not settings.*_backend. A developer's local
    .env can set e.g. VIDEO_GEN_BACKEND=fake to run the actual pipeline for
    free (see tools/video_gen.py's FakeVideoBackend and friends); Settings
    reads .env unconditionally, so without this, that same override would
    silently swap in the *fake* backend during tests too, bypassing the
    test's mock entirely and testing the wrong code path. Pinning these
    back to their real defaults for every test keeps the suite's behavior
    independent of whatever's in the developer's .env.
    """
    monkeypatch.setattr(settings, "video_gen_backend", "kling")
    monkeypatch.setattr(settings, "voice_backend", "elevenlabs")
    monkeypatch.setattr(settings, "transcribe_backend", "deepgram")
    monkeypatch.setattr(settings, "quality_review_backend", "gemini")


def _make_synthetic_clip(path: Path, duration: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={duration}:size=320x240:rate=10",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            "-shortest",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def _make_synthetic_audio(path: Path, duration: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=220:duration={duration}",
            "-c:a",
            "libmp3lame",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def synthetic_clip_factory(tmp_path):
    def _factory(name: str, duration: float = 2.0) -> Path:
        path = tmp_path / name
        _make_synthetic_clip(path, duration)
        return path

    return _factory


@pytest.fixture
def synthetic_audio_factory(tmp_path):
    def _factory(name: str, duration: float = 6.0) -> Path:
        path = tmp_path / name
        _make_synthetic_audio(path, duration)
        return path

    return _factory
