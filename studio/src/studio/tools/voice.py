"""ElevenLabs voice synthesis. Rotates through a per-channel voice pool
(blueprint.md Section 4.4: "never one static voice reused verbatim across
every video").

Fish Audio / Chatterbox cost-fallback (same section) isn't implemented in
Phase 1 — same scoping call as Video Generation shipping Kling only: one
real backend behind a small interface that can grow a second one later,
rather than two half-built integrations now.

API shape confirmed against the installed elevenlabs==2.58.0 SDK, not
guessed: `client.text_to_speech.convert(voice_id, text=..., model_id=...)`
returns `Iterator[bytes]`.
"""

import logging
from typing import Protocol

from elevenlabs.client import ElevenLabs

from studio.config import settings

log = logging.getLogger(__name__)

# A small rotating pool, not one static voice. These are ElevenLabs'
# standard pre-made voice IDs as of this project's training cutoff —
# verify they're still valid in your account before relying on this live.
VOICE_POOL = [
    "21m00Tcm4TlvDq8ikWAM",  # Rachel
    "29vD33N1CtxCmqQRPOHJ",  # Drew
    "2EiwWnXFnvU5JabPnv8n",  # Clyde
]

MODEL_ID = "eleven_multilingual_v2"


class TTSBackend(Protocol):
    def synthesize(self, text: str, voice_id: str) -> bytes: ...


class ElevenLabsBackend:
    def __init__(self) -> None:
        if not settings.elevenlabs_api_key:
            raise RuntimeError(
                "ELEVENLABS_API_KEY missing — Voice Synthesis needs it. Get a "
                "key at elevenlabs.io and add it to .env."
            )
        self._client = ElevenLabs(api_key=settings.elevenlabs_api_key)

    def synthesize(self, text: str, voice_id: str) -> bytes:
        chunks = self._client.text_to_speech.convert(
            voice_id, text=text, model_id=MODEL_ID, output_format="mp3_44100_128"
        )
        return b"".join(chunks)


def voice_for_video(video_id: str) -> str:
    """Deterministic rotation, not random: the same video maps to the same
    voice across a retry, but different videos spread across the pool."""
    index = int(str(video_id).replace("-", ""), 16) % len(VOICE_POOL)
    return VOICE_POOL[index]
