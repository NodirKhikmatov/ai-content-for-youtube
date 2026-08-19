"""Orchestrates a YouTube Shorts cut (vertical, ~45-60s) for a video that
has already been through Storytelling — shared by scripts/make_short.py's
CLI and web/runner.py's dashboard, so the two don't drift onto different
assembly logic. See agents/shorts_script.py's module docstring for why the
short's narration is its own hook-first prose, not a truncation of the
long-form script.
"""

import logging
from pathlib import Path
from typing import Any

from studio import db
from studio.agents import shorts_script
from studio.agents.subtitle import words_to_srt
from studio.config import settings
from studio.tools.ffmpeg_utils import (
    burn_subtitles,
    extract_audio,
    match_video_to_audio_duration,
    mux_audio_over_video,
    probe_duration_seconds,
)
from studio.tools.transcribe import fake_transcribe, transcribe
from studio.tools.video_gen import FakeVideoBackend, HiggsfieldBackend, KlingBackend
from studio.tools.voice import ElevenLabsBackend, FakeTTSBackend, voice_for_video

log = logging.getLogger(__name__)

MEDIA_DIR = Path("media")


def _make_video_backend():
    if settings.video_gen_backend == "fake":
        return FakeVideoBackend()
    if settings.video_gen_backend == "higgsfield":
        return HiggsfieldBackend()
    return KlingBackend()


def _make_voice_backend():
    if settings.voice_backend == "fake":
        return FakeTTSBackend()
    return ElevenLabsBackend()


def make_short_video(video_id: str) -> dict[str, Any]:
    video = db.get_video(video_id)
    beat_sheet = db.get_latest_agent_output(video_id, "storytelling")
    if not beat_sheet:
        raise RuntimeError(
            f"No storytelling output for video {video_id} — run the main pipeline first."
        )

    work_dir = MEDIA_DIR / str(video_id) / "shorts"
    work_dir.mkdir(parents=True, exist_ok=True)

    log.info("shorts: writing shorts script")
    narration = shorts_script.run(video_id, str(video["case_id"]), beat_sheet)

    log.info("shorts: synthesizing voice")
    voice_path = work_dir / "voice.mp3"
    voice_id = voice_for_video(video_id)
    voice_path.write_bytes(_make_voice_backend().synthesize(narration, voice_id))
    narration_seconds = probe_duration_seconds(voice_path)

    log.info("shorts: generating vertical clip (%.1fs)", narration_seconds)
    clip_path = work_dir / "clip.mp4"
    clip_path.write_bytes(
        _make_video_backend().generate_clip(
            narration, int(narration_seconds) + 1, aspect_ratio="9:16"
        )
    )

    from studio.tools.audio_fx import mix_master_soundtrack

    matched_path = work_dir / "matched.mp4"
    master_audio_path = work_dir / "master_audio.aac"
    assembled_path = work_dir / "assembled.mp4"
    try:
        match_video_to_audio_duration(clip_path, narration_seconds, matched_path)

        case = db.get_case(video["case_id"]) if video.get("case_id") else None
        jurisdiction = (case.get("jurisdiction") or "").lower() if case else ""
        is_webtoon = any(k in jurisdiction for k in ("webtoon", "manhwa", "manga", "anime"))

        mix_master_soundtrack(
            voice_path=voice_path,
            out_path=master_audio_path,
            is_webtoon=is_webtoon,
            bgm_volume=settings.bgm_volume,
            enable_bgm=settings.bgm_enabled,
        )

        mux_audio_over_video(matched_path, master_audio_path, assembled_path)
    finally:
        master_audio_path.unlink(missing_ok=True)
        matched_path.unlink(missing_ok=True)

    log.info("shorts: transcribing for captions")
    extracted_audio_path = work_dir / "for_transcription.mp3"
    extract_audio(assembled_path, extracted_audio_path)
    try:
        if settings.transcribe_backend == "fake":
            result = fake_transcribe(extracted_audio_path, narration)
        else:
            result = transcribe(extracted_audio_path.read_bytes())
    finally:
        extracted_audio_path.unlink(missing_ok=True)

    srt_path = work_dir / "captions.srt"
    srt_path.write_text(words_to_srt(result["words"]))

    final_path = work_dir / "short.mp4"
    try:
        burn_subtitles(assembled_path, srt_path, final_path)
    except Exception as exc:
        log.warning("shorts: burn-in failed, keeping un-captioned cut (%s)", exc)
        final_path = assembled_path

    output = {
        "narration": narration,
        "final_path": str(final_path),
        "narration_seconds": narration_seconds,
    }
    db.record_agent_run(
        video_id,
        "shorts_assembly",
        "succeeded",
        input={"narration_words": len(narration.split())},
        output=output,
    )
    log.info("shorts: ready — %s (%.1fs)", final_path, narration_seconds)
    return output
