"""Video Assembly / Editor agent. See blueprint.md Section 4.4.

blueprint.md's spec lists "subtitle timing" among this agent's inputs, but
in this Phase 1 graph Video Assembly runs *before* Subtitle
(... -> video_generation -> video_assembly -> subtitle -> ...), so there's
no caption timing yet to consume — the same kind of spec/graph-order
mismatch Originality's Day 3 docstring flagged for "draft script". The
resolution here mirrors that one: this agent assembles voice + visuals
only; Subtitle forced-aligns against *this* agent's output afterward and
produces the final captioned cut. That's arguably the more correct order
anyway — forced alignment wants the final mixed audio, not a pre-assembly
guess at timing.

Pacing rule enforced concretely, not just as a prompt ask: concatenates the
per-beat clips in order, then stretches or trims the concatenated visual
track to match the narration's exact duration (loop the last clip if
visuals run short, trim if they run long) — no dead air past the end of
narration, no narration playing over a frozen last frame.
"""

import logging
from pathlib import Path

from studio import db, storage
from studio.state import PipelineState
from studio.tools.ffmpeg_utils import (
    concat_clips,
    match_video_to_audio_duration,
    mux_audio_over_video,
    probe_duration_seconds,
)

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
    voice_audio_path = state.get("voice_audio_path")
    clip_paths = state.get("video_clip_paths")

    if not voice_audio_path:
        raise RuntimeError(
            "No voice_audio_path in state — Voice Synthesis must run before Video Assembly."
        )
    if not clip_paths:
        raise RuntimeError(
            "No video_clip_paths in state — Video Generation must run before Video Assembly."
        )

    work_dir = MEDIA_DIR / str(video_id)
    work_dir.mkdir(parents=True, exist_ok=True)
    concatenated_path = work_dir / "concatenated.mp4"
    matched_path = work_dir / "matched.mp4"
    assembled_path = work_dir / "assembled.mp4"

    try:
        concat_clips([Path(p) for p in clip_paths], concatenated_path)

        narration_seconds = probe_duration_seconds(Path(voice_audio_path))
        match_video_to_audio_duration(concatenated_path, narration_seconds, matched_path)

        mux_audio_over_video(matched_path, Path(voice_audio_path), assembled_path)
    except Exception as exc:
        db.record_agent_run(video_id, "video_assembly", "failed", error=str(exc))
        raise
    finally:
        concatenated_path.unlink(missing_ok=True)
        matched_path.unlink(missing_ok=True)

    r2_key = f"videos/{video_id}/assembled.mp4"
    uploaded = _best_effort_upload(assembled_path, r2_key)

    db.update_video(video_id, status="produced", assembled_video_path=str(assembled_path))
    db.record_agent_run(
        video_id,
        "video_assembly",
        "succeeded",
        input={"clip_count": len(clip_paths), "narration_seconds": narration_seconds},
        output={"local_path": str(assembled_path), "r2_key": r2_key if uploaded else None},
    )

    log.info(
        "video_assembly: %s (%d clips, %.1fs narration)",
        assembled_path,
        len(clip_paths),
        narration_seconds,
    )

    state["assembled_video_path"] = str(assembled_path)
    return state
