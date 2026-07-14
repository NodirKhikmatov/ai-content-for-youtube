"""Video / Visual Generation agent. See blueprint.md Section 4.4.

One Kling clip per beat from Storytelling's beat sheet (six beats -> six
clips), using each beat's guidance text as the generation prompt. Veo for
hero shots is not implemented in Phase 1 — see tools/video_gen.py's module
docstring; the backend sits behind VideoGenBackend specifically so adding
it later doesn't touch this agent.

Local disk is the working store, same reasoning as Voice Synthesis: R2
upload is best-effort, not a gate, since every clip needs to be locally
readable by ffmpeg in Video Assembly regardless.

A failed clip generation raises rather than silently producing a shorter
video — Video Assembly has no sensible way to fill in for a missing beat's
visuals.
"""

import logging
from pathlib import Path

from studio import db, storage
from studio.state import PipelineState
from studio.tools.video_gen import KlingBackend

log = logging.getLogger(__name__)

MEDIA_DIR = Path("media")
CLIP_DURATION_SECONDS = 5


def _best_effort_upload(local_path: Path, r2_key: str) -> bool:
    try:
        storage.upload_file(str(local_path), r2_key)
        return True
    except Exception as exc:
        log.warning("R2 upload skipped for %s: %s", r2_key, exc)
        return False


def run(state: PipelineState) -> PipelineState:
    video_id = state["video_id"]
    beat_sheet = state.get("beat_sheet")
    if not beat_sheet or not beat_sheet.get("beats"):
        raise RuntimeError(
            "No beat sheet in state — Storytelling must run before Video Generation."
        )

    clip_dir = MEDIA_DIR / str(video_id) / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)

    clip_paths: list[str] = []
    try:
        backend = KlingBackend()
        for i, beat in enumerate(beat_sheet["beats"]):
            clip_bytes = backend.generate_clip(beat["content"], CLIP_DURATION_SECONDS)
            local_path = clip_dir / f"{i:02d}_{beat['name']}.mp4"
            local_path.write_bytes(clip_bytes)
            clip_paths.append(str(local_path))
    except Exception as exc:
        db.record_agent_run(video_id, "video_generation", "failed", error=str(exc))
        raise

    uploaded = 0
    for path in clip_paths:
        r2_key = f"videos/{video_id}/clips/{Path(path).name}"
        if _best_effort_upload(Path(path), r2_key):
            uploaded += 1

    db.record_agent_run(
        video_id,
        "video_generation",
        "succeeded",
        input={"beat_count": len(beat_sheet["beats"])},
        output={"clip_paths": clip_paths, "uploaded_to_r2": uploaded},
    )

    log.info("video_generation: %d clips (%d uploaded to R2)", len(clip_paths), uploaded)

    state["video_clip_paths"] = clip_paths
    return state
