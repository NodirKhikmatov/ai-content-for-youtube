"""Deepgram forced transcription — the Subtitle agent's word-timestamp
source (blueprint.md Section 4.4 names WhisperX or Deepgram; Deepgram is
chosen here specifically because it's a hosted API with a small, stable
REST surface, rather than WhisperX's heavy local torch/model-download
footprint, which is a poor fit for a scaffold meant to run on a laptop
without a GPU).

Direct REST call via httpx, no SDK dependency — same reasoning as Tavily
(tools/search.py): one stable endpoint, one dependency saved.
"""

from pathlib import Path
from typing import Any, TypedDict

import httpx

from studio.config import settings
from studio.tools.ffmpeg_utils import probe_duration_seconds
from studio.tools.retry import with_retry

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"


class Word(TypedDict):
    word: str
    start: float
    end: float


class TranscriptResult(TypedDict):
    transcript: str
    words: list[Word]


def transcribe(audio_bytes: bytes, mimetype: str = "audio/mpeg") -> TranscriptResult:
    if not settings.deepgram_api_key:
        raise RuntimeError(
            "DEEPGRAM_API_KEY missing — Subtitle needs it for forced "
            "alignment. Get a key at deepgram.com and add it to .env."
        )

    def _call() -> httpx.Response:
        response = httpx.post(
            DEEPGRAM_URL,
            headers={
                "Authorization": f"Token {settings.deepgram_api_key}",
                "Content-Type": mimetype,
            },
            params={"model": "nova-2", "smart_format": "true", "punctuate": "true"},
            content=audio_bytes,
            timeout=120.0,
        )
        response.raise_for_status()
        return response

    data: dict[str, Any] = with_retry(_call).json()
    alt = data["results"]["channels"][0]["alternatives"][0]
    words: list[Word] = [
        {"word": w["word"], "start": w["start"], "end": w["end"]} for w in alt.get("words", [])
    ]
    return {"transcript": alt.get("transcript", ""), "words": words}


def fake_transcribe(audio_path: Path, script: str) -> TranscriptResult:
    """Local stand-in for Deepgram: no API key, no network call, no actual
    speech recognition. Fabricates evenly-spaced word timestamps across the
    audio file's real duration (via ffprobe) using the script text that's
    already known to have been spoken, rather than transcribing anything.
    The "transcript" is the script itself, so word_error_rate always comes
    out to 0 and Subtitle's burn-in path always runs. Only meaningful when
    the narration audio was actually synthesized from this exact script —
    see TRANSCRIBE_BACKEND in .env.example.
    """
    duration = probe_duration_seconds(audio_path)
    script_words = script.split()
    if not script_words:
        return {"transcript": "", "words": []}
    per_word = duration / len(script_words)
    words: list[Word] = [
        {"word": w, "start": i * per_word, "end": (i + 1) * per_word}
        for i, w in enumerate(script_words)
    ]
    return {"transcript": script, "words": words}
