"""Shared fixtures for the Day 5 media agents. ffmpeg is installed locally
(unlike ElevenLabs/Kling/Deepgram, which need paid API keys this project
doesn't have), so these generate real tiny synthetic clips/audio via
ffmpeg's lavfi sources — real ffmpeg orchestration gets tested here, not
just mocked.
"""

import subprocess
from pathlib import Path

import pytest


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
