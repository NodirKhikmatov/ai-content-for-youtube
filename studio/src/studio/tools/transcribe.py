"""Deepgram forced transcription — the Subtitle agent's word-timestamp
source (blueprint.md Section 4.4 names WhisperX or Deepgram; Deepgram is
chosen here specifically because it's a hosted API with a small, stable
REST surface, rather than WhisperX's heavy local torch/model-download
footprint, which is a poor fit for a scaffold meant to run on a laptop
without a GPU).

Direct REST call via httpx, no SDK dependency — same reasoning as Tavily
(tools/search.py): one stable endpoint, one dependency saved.
"""

from typing import Any, TypedDict

import httpx

from studio.config import settings
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
