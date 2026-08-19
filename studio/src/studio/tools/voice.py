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
import subprocess
import tempfile
from pathlib import Path
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

# Character role mapping for multi-character voice acting
CHARACTER_VOICES = {
    "narrator": "21m00Tcm4TlvDq8ikWAM",   # Rachel / Grounded Storyteller
    "hero": "ErXwobaYiN019PkySvjV",       # Antoni / High Energy Protagonist
    "villain": "VR6AewLTigWG4xSOukaG",    # Arnold / Deep Menacing Antagonist
    "system_ai": "EXAVITQu4vr4xnSDxMaL",  # Bella / Status Notification
}

# macOS system voices for offline zero-cost multi-character testing
FAKE_ROLE_VOICES = {
    "narrator": "Daniel",
    "hero": "Samantha",
    "villain": "Fred",
    "system_ai": "Victoria",
}

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


class FakeTTSBackend:
    """Local, zero-cost stand-in for ElevenLabsBackend: same TTSBackend
    interface, but synthesizes narration with macOS's built-in `say`
    command instead of calling ElevenLabs — no API key, no network call,
    no bill, no per-voice API permissions to hit.
    """

    def synthesize(self, text: str, voice_id: str = "narrator") -> bytes:
        with tempfile.TemporaryDirectory() as tmp_dir:
            aiff_path = Path(tmp_dir) / "voice.aiff"
            mp3_path = Path(tmp_dir) / "voice.mp3"

            sys_voice = FAKE_ROLE_VOICES.get(voice_id, "Daniel")
            say_args = ["say"]
            # Check if voice is specified
            if sys_voice:
                say_args.extend(["-v", sys_voice])
            say_args.extend(["-o", str(aiff_path), text])

            say_result = subprocess.run(
                say_args,
                capture_output=True,
                text=True,
            )
            # If named voice isn't installed on system, fallback to default say
            if say_result.returncode != 0:
                say_result = subprocess.run(
                    ["say", "-o", str(aiff_path), text],
                    capture_output=True,
                    text=True,
                )
            if say_result.returncode != 0:
                raise RuntimeError(f"macOS 'say' failed: {say_result.stderr[-2000:]}")

            ffmpeg_result = subprocess.run(
                [settings.ffmpeg_binary, "-y", "-i", str(aiff_path), "-c:a", "libmp3lame", str(mp3_path)],
                capture_output=True,
                text=True,
            )
            if ffmpeg_result.returncode != 0:
                raise RuntimeError(
                    f"ffmpeg failed converting fake voice to mp3: {ffmpeg_result.stderr[-2000:]}"
                )
            return mp3_path.read_bytes()


def voice_for_video(video_id: str) -> str:
    """Deterministic rotation, not random: the same video maps to the same
    voice across a retry, but different videos spread across the pool."""
    index = int(str(video_id).replace("-", ""), 16) % len(VOICE_POOL)
    return VOICE_POOL[index]


def voice_for_role(role: str, fallback_voice: str) -> str:
    """Returns the matching voice ID for a specific dialogue role."""
    return CHARACTER_VOICES.get(role, fallback_voice)
