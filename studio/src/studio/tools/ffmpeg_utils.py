"""ffmpeg subprocess helpers shared by Video Assembly and Subtitle — both
need "run ffmpeg, check it succeeded, raise with the real stderr on
failure" often enough that duplicating it per agent would just be two
places to get the error handling subtly wrong.

Binary paths come from settings.ffmpeg_binary/ffprobe_binary rather than a
hardcoded "ffmpeg"/"ffprobe" — plain Homebrew ffmpeg has no libass support,
so burn_subtitles() needs a libass-enabled build (`ffmpeg-full`) pointed at
explicitly. See config.py and README.md.
"""

import json
import logging
import subprocess
from pathlib import Path

from studio.config import settings

log = logging.getLogger(__name__)


class FfmpegError(RuntimeError):
    pass


def _run(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise FfmpegError(f"{args[0]} failed ({result.returncode}): {result.stderr[-2000:]}")


def probe_duration_seconds(path: Path) -> float:
    result = subprocess.run(
        [
            settings.ffprobe_binary,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise FfmpegError(f"ffprobe failed ({result.returncode}): {result.stderr[-2000:]}")
    return float(json.loads(result.stdout)["format"]["duration"])


def concat_clips(clip_paths: list[Path], out_path: Path) -> None:
    """Concatenates video-only clips end to end. All clips must share
    codec/resolution — true of same-vendor Kling output, which is all this
    project generates in Phase 1."""
    if not clip_paths:
        raise FfmpegError("concat_clips called with no clips")
    concat_list = out_path.with_suffix(".concat.txt")
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in clip_paths))
    try:
        _run(
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
                str(out_path),
            ]
        )
    finally:
        concat_list.unlink(missing_ok=True)


def match_video_to_audio_duration(video_path: Path, target_seconds: float, out_path: Path) -> None:
    """Loops (if short) or trims (if long) so the visual track's duration
    matches the narration's exactly — no dead air past the end of the
    narration, no narration playing over a frozen last frame."""
    video_seconds = probe_duration_seconds(video_path)
    if video_seconds >= target_seconds:
        _run(
            [
                settings.ffmpeg_binary,
                "-y",
                "-i",
                str(video_path),
                "-t",
                f"{target_seconds:.3f}",
                "-c",
                "copy",
                str(out_path),
            ]
        )
        return

    loops_needed = int(target_seconds // video_seconds) + 1
    _run(
        [
            settings.ffmpeg_binary,
            "-y",
            "-stream_loop",
            str(loops_needed),
            "-i",
            str(video_path),
            "-t",
            f"{target_seconds:.3f}",
            "-c",
            "copy",
            str(out_path),
        ]
    )


def mux_audio_over_video(video_path: Path, audio_path: Path, out_path: Path) -> None:
    _run(
        [
            settings.ffmpeg_binary,
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(out_path),
        ]
    )


def extract_audio(video_or_audio_path: Path, out_path: Path) -> None:
    _run(
        [
            settings.ffmpeg_binary,
            "-y",
            "-i",
            str(video_or_audio_path),
            "-vn",
            "-acodec",
            "libmp3lame",
            str(out_path),
        ]
    )


def burn_subtitles(video_path: Path, srt_path: Path, out_path: Path) -> None:
    # ffmpeg's subtitles filter wants the srt path as a plain filter
    # argument; colons in absolute Windows-style paths would need escaping,
    # but this project only ever runs on POSIX paths. Requires a
    # libass-enabled ffmpeg build — see the module docstring.
    _run(
        [
            settings.ffmpeg_binary,
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"subtitles={srt_path}",
            "-c:a",
            "copy",
            str(out_path),
        ]
    )
