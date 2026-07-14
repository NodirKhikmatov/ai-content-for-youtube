"""Subtitle / Caption agent. See blueprint.md Section 4.4.

Extracts the assembled video's actual audio track (not the pre-mux
narration file) and forced-aligns it with Deepgram, so caption timing
matches what viewers will actually hear rather than an earlier artifact
assumed identical. Generates an .srt file and, when word-error-rate against
the source script is low enough, burns captions in to produce the final
cut.

Failure handling: word-error-rate above WER_THRESHOLD does not block the
pipeline — there's no manual-correction gate node to route into yet, the
same situation Originality was in on Day 3. It sets
`needs_manual_correction` in state/output and skips burn-in, leaving the
un-captioned assembled cut in place rather than publishing captions that
likely don't match the audio.
"""

import logging
from pathlib import Path
from typing import Any

from studio import db, storage
from studio.state import PipelineState
from studio.tools.ffmpeg_utils import burn_subtitles, extract_audio
from studio.tools.transcribe import Word, transcribe

log = logging.getLogger(__name__)

MEDIA_DIR = Path("media")
WER_THRESHOLD = 0.15
MAX_WORDS_PER_LINE = 8
MAX_SECONDS_PER_LINE = 4.0


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Standard word-level Levenshtein distance / reference length."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    n, m = len(ref_words), len(hyp_words)
    if n == 0:
        return 0.0 if m == 0 else 1.0

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i - 1].lower() == hyp_words[j - 1].lower():
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[n][m] / n


def _format_srt_timestamp(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, total_ms = divmod(total_ms, 3_600_000)
    minutes, total_ms = divmod(total_ms, 60_000)
    secs, ms = divmod(total_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def words_to_srt(words: list[Word]) -> str:
    if not words:
        return ""
    entries: list[list[Word]] = []
    chunk: list[Word] = []
    chunk_start = words[0]["start"]
    for w in words:
        if chunk and (
            len(chunk) >= MAX_WORDS_PER_LINE or (w["end"] - chunk_start) > MAX_SECONDS_PER_LINE
        ):
            entries.append(chunk)
            chunk = []
            chunk_start = w["start"]
        chunk.append(w)
    if chunk:
        entries.append(chunk)

    blocks = []
    for i, entry in enumerate(entries, start=1):
        start, end = entry[0]["start"], entry[-1]["end"]
        text = " ".join(w["word"] for w in entry)
        blocks.append(
            f"{i}\n{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}\n{text}\n"
        )
    return "\n".join(blocks)


def _best_effort_upload(local_path: Path, r2_key: str) -> bool:
    try:
        storage.upload_file(str(local_path), r2_key)
        return True
    except Exception as exc:
        log.warning("R2 upload skipped for %s: %s", r2_key, exc)
        return False


def run(state: PipelineState) -> PipelineState:
    video_id = state["video_id"]
    assembled_video_path = state.get("assembled_video_path")
    script = state.get("script")

    if not assembled_video_path:
        raise RuntimeError(
            "No assembled_video_path in state — Video Assembly must run before Subtitle."
        )
    if not script:
        raise RuntimeError("No script in state — cannot compute word-error-rate without it.")

    work_dir = MEDIA_DIR / str(video_id)
    work_dir.mkdir(parents=True, exist_ok=True)
    extracted_audio_path = work_dir / "for_transcription.mp3"
    srt_path = work_dir / "captions.srt"
    captioned_path = work_dir / "final.mp4"

    try:
        extract_audio(Path(assembled_video_path), extracted_audio_path)
        result = transcribe(extracted_audio_path.read_bytes())
        wer = word_error_rate(script, result["transcript"])
        srt_path.write_text(words_to_srt(result["words"]))
    except Exception as exc:
        db.record_agent_run(video_id, "subtitle", "failed", error=str(exc))
        raise
    finally:
        extracted_audio_path.unlink(missing_ok=True)

    needs_manual_correction = wer > WER_THRESHOLD
    final_path = assembled_video_path

    if not needs_manual_correction:
        try:
            burn_subtitles(Path(assembled_video_path), srt_path, captioned_path)
            final_path = str(captioned_path)
        except Exception as exc:
            log.warning("subtitle: burn-in failed, keeping un-captioned cut (%s)", exc)

    uploaded_srt = _best_effort_upload(srt_path, f"videos/{video_id}/captions.srt")
    uploaded_video = (
        _best_effort_upload(Path(final_path), f"videos/{video_id}/final.mp4")
        if final_path != assembled_video_path
        else False
    )

    update_fields: dict[str, Any] = {"status": "in_review", "subtitle_path": str(srt_path)}
    if final_path != assembled_video_path:
        update_fields["assembled_video_path"] = final_path
    db.update_video(video_id, **update_fields)

    db.record_agent_run(
        video_id,
        "subtitle",
        "succeeded",
        input={"script_words": len(script.split())},
        output={
            "wer": wer,
            "needs_manual_correction": needs_manual_correction,
            "srt_path": str(srt_path),
            "final_video_path": final_path,
            "uploaded_srt": uploaded_srt,
            "uploaded_video": uploaded_video,
        },
    )

    log.info(
        "subtitle: WER=%.3f (threshold=%.2f), needs_manual_correction=%s",
        wer,
        WER_THRESHOLD,
        needs_manual_correction,
    )

    state["subtitle_path"] = str(srt_path)
    state["assembled_video_path"] = final_path
    return state
