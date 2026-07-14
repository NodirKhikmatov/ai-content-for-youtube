"""Voice Synthesis agent. See blueprint.md Section 4.4.

Synthesizes the full script with ElevenLabs, using a deterministic
per-video pick from a rotating voice pool (tools/voice.py) rather than one
static voice for every video.

Local disk (media/{video_id}/) is the canonical working store during a
pipeline run — every downstream agent (Video Assembly, Subtitle) needs
these files locally for ffmpeg anyway, and there's no live R2 credential to
test an upload-as-gate design against. R2 upload is attempted as best-effort
persistence and logged, but a failed or unconfigured upload does not fail
the agent — the local path remains valid and is what state/DB actually
track. blueprint.md Section 5.2 describes R2 as the eventual durable store;
this is a deliberate Phase 1 scoping call, not an oversight.

Failure handling: blueprint.md's spec calls for falling back to a second
TTS vendor on outage. Only ElevenLabs is implemented in Phase 1 (see
tools/voice.py's module docstring for why); a synthesis failure here raises
rather than silently producing no audio, since every downstream agent
depends on this file existing.
"""

import logging
from pathlib import Path

from studio import db, storage
from studio.state import PipelineState
from studio.tools.voice import ElevenLabsBackend, voice_for_video

log = logging.getLogger(__name__)

MEDIA_DIR = Path("media")


def _best_effort_upload(local_path: Path, r2_key: str) -> bool:
    try:
        storage.upload_file(str(local_path), r2_key)
        return True
    except Exception as exc:
        log.warning("R2 upload skipped for %s: %s", r2_key, exc)
        return False


def run(state: PipelineState) -> PipelineState:
    video_id = state["video_id"]
    script = state.get("script")
    if not script:
        raise RuntimeError("No script in state — Script Writer must run before Voice Synthesis.")

    voice_id = voice_for_video(video_id)
    local_path = MEDIA_DIR / str(video_id) / "voice.mp3"
    local_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        backend = ElevenLabsBackend()
        audio_bytes = backend.synthesize(script, voice_id)
        local_path.write_bytes(audio_bytes)
    except Exception as exc:
        db.record_agent_run(video_id, "voice_synthesis", "failed", error=str(exc))
        raise

    r2_key = f"videos/{video_id}/voice.mp3"
    uploaded = _best_effort_upload(local_path, r2_key)

    db.update_video(video_id, voice_audio_path=str(local_path))
    db.record_agent_run(
        video_id,
        "voice_synthesis",
        "succeeded",
        input={"voice_id": voice_id, "script_words": len(script.split())},
        output={"local_path": str(local_path), "r2_key": r2_key if uploaded else None},
    )

    log.info("voice_synthesis: %s (voice=%s, r2=%s)", local_path, voice_id, uploaded)

    state["voice_audio_path"] = str(local_path)
    return state
