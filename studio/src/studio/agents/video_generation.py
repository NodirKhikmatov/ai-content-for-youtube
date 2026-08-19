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
from studio.config import settings
from studio.state import PipelineState
from studio.tools.video_gen import FakeVideoBackend, HiggsfieldBackend, KlingBackend

log = logging.getLogger(__name__)

MEDIA_DIR = Path("media")
CLIP_DURATION_SECONDS = 5


def _make_backend():
    if settings.video_gen_backend == "fake":
        return FakeVideoBackend()
    if settings.video_gen_backend == "higgsfield":
        return HiggsfieldBackend()
    return KlingBackend()


def _best_effort_upload(local_path: Path, r2_key: str) -> bool:
    try:
        storage.upload_file(str(local_path), r2_key)
        return True
    except Exception as exc:
        log.warning("R2 upload skipped for %s: %s", r2_key, exc)
        return False


def _is_webtoon(case: dict | None) -> bool:
    if not case:
        return False
    jurisdiction = (case.get("jurisdiction") or "").lower()
    return any(k in jurisdiction for k in ("webtoon", "manhwa", "manga", "anime", "recap", "comic"))


def _prompt_for_beat(beat: dict, case: dict | None) -> str:
    content = beat["content"]
    if _is_webtoon(case):
        return (
            f"{content}, high quality Korean manhwa style, Solo Leveling anime aesthetic, "
            f"glowing vibrant magical aura, sharp comic linework, dynamic anime camera angle, "
            f"vibrant cell shaded lighting, masterpiece 8k, ArtStation trending"
        )
    return content


def run(state: PipelineState) -> PipelineState:
    video_id = state["video_id"]
    case = db.get_case(state["case_id"]) if state.get("case_id") else None
    beat_sheet = state.get("beat_sheet")
    if not beat_sheet or not beat_sheet.get("beats"):
        raise RuntimeError(
            "No beat sheet in state — Storytelling must run before Video Generation."
        )

    clip_dir = MEDIA_DIR / str(video_id) / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)

    clip_paths: list[str] = []
    try:
        backend = _make_backend()
        for i, beat in enumerate(beat_sheet["beats"]):
            prompt = _prompt_for_beat(beat, case)
            clip_bytes = backend.generate_clip(prompt, CLIP_DURATION_SECONDS)
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

    # Return only this node's new key, not the whole accumulated state:
    # this runs concurrently with voice_synthesis (both fork off
    # script_writer, both join into video_assembly), and if both nodes
    # returned every key they'd merely passed through unchanged (case_id,
    # script, ...), LangGraph would see two writes to the same channel in
    # the same step and raise InvalidUpdateError, even though the values
    # are identical.
    return {"video_clip_paths": clip_paths}
