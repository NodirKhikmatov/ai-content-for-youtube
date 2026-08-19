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
import subprocess
from pathlib import Path

from studio import db, storage
from studio.config import settings
from studio.state import PipelineState
from studio.tools.dialogue_parser import parse_dialogue_segments
from studio.tools.voice import ElevenLabsBackend, FakeTTSBackend, voice_for_role, voice_for_video

log = logging.getLogger(__name__)

MEDIA_DIR = Path("media")


def _make_backend():
    if settings.voice_backend == "fake":
        return FakeTTSBackend()
    return ElevenLabsBackend()


def _concat_audio_files(audio_files: list[Path], output_file: Path) -> None:
    """Concatenates multiple audio segment files into one seamless audio track."""
    concat_list = output_file.with_suffix(".concat.txt")
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in audio_files))
    try:
        subprocess.run(
            [
                settings.ffmpeg_binary,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c",
                "copy",
                str(output_file),
            ],
            check=True,
            capture_output=True,
        )
    finally:
        concat_list.unlink(missing_ok=True)


def run(state: PipelineState) -> PipelineState:
    video_id = state["video_id"]
    script = state.get("script")
    if not script:
        raise RuntimeError("No script in state — Script Writer must run before Voice Synthesis.")

    default_voice_id = voice_for_video(video_id)
    work_dir = MEDIA_DIR / str(video_id)
    work_dir.mkdir(parents=True, exist_ok=True)
    local_path = work_dir / "voice.mp3"

    segments = parse_dialogue_segments(script)
    backend = _make_backend()

    try:
        if len(segments) > 1:
            log.info("voice_synthesis: multi-character dialogue detected (%d segments)", len(segments))
            seg_files: list[Path] = []
            for i, seg in enumerate(segments):
                seg_path = work_dir / f"voice_seg_{i}.mp3"
                role_voice = voice_for_role(seg["role"], default_voice_id)
                seg_audio = backend.synthesize(seg["text"], role_voice)
                seg_path.write_bytes(seg_audio)
                seg_files.append(seg_path)

            _concat_audio_files(seg_files, local_path)
            for f in seg_files:
                f.unlink(missing_ok=True)
        else:
            audio_bytes = backend.synthesize(script, default_voice_id)
            local_path.write_bytes(audio_bytes)
    except Exception as exc:
        db.record_agent_run(video_id, "voice_synthesis", "failed", error=str(exc))
        raise

    r2_key = f"videos/{video_id}/voice.mp3"
    uploaded = storage.best_effort_upload(local_path, r2_key)

    unique_roles = list({s["role"] for s in segments})
    db.update_video(video_id, voice_audio_path=str(local_path))
    db.record_agent_run(
        video_id,
        "voice_synthesis",
        "succeeded",
        input={"voice_id": default_voice_id, "script_words": len(script.split()), "roles": unique_roles},
        output={"local_path": str(local_path), "r2_key": r2_key if uploaded else None, "roles": unique_roles},
    )

    log.info("voice_synthesis: %s (roles=%s, voice=%s, r2=%s)", local_path, unique_roles, default_voice_id, uploaded)

    return {"voice_audio_path": str(local_path)}
