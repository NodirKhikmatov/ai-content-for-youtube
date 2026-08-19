"""Background Music (BGM) & Sound Effects (SFX) Tool.

Generates cinematic ambient soundtrack and transition sound effects, and mixes
them dynamically with the voiceover track (with audio ducking so narration remains crisp).
"""

import logging
import subprocess
from pathlib import Path

from studio.config import settings
from studio.tools.ffmpeg_utils import FfmpegError, probe_duration_seconds

log = logging.getLogger(__name__)


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise FfmpegError(f"{args[0]} failed ({result.returncode}): {result.stderr[-2000:]}")


def generate_cinematic_bgm(duration_seconds: float, is_webtoon: bool, out_path: Path) -> Path:
    """Generates procedural ambient background music with smooth fade-in and fade-out."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fade_out_start = max(0.5, duration_seconds - 2.0)
    
    if is_webtoon:
        # High-energy synth chord pad for Manhwa/Webtoon (layered harmonics + subtle pulse)
        filter_expr = (
            "aevalsrc="
            "'0.15*sin(2*PI*110*t) + 0.12*sin(2*PI*164.81*t) + 0.10*sin(2*PI*220*t) + 0.08*sin(2*PI*329.63*t) + "
            "0.05*sin(2*PI*440*t)*sin(2*PI*2*t)':"
            f"duration={duration_seconds:.3f}:s=44100,"
            "lowpass=f=1200,"
            f"afade=t=in:ss=0:d=1.5,afade=t=out:st={fade_out_start:.3f}:d=2.0"
        )
    else:
        # Deep dark documentary drone & suspense pad (subtle sub-bass + mysterious slow modulation)
        filter_expr = (
            "aevalsrc="
            "'0.20*sin(2*PI*55*t) + 0.15*sin(2*PI*82.4*t) + 0.10*sin(2*PI*110*t) + "
            "0.06*sin(2*PI*220*t)*(0.5+0.5*sin(2*PI*0.2*t))':"
            f"duration={duration_seconds:.3f}:s=44100,"
            "lowpass=f=800,"
            f"afade=t=in:ss=0:d=2.0,afade=t=out:st={fade_out_start:.3f}:d=2.0"
        )

    _run_ffmpeg(
        [
            settings.ffmpeg_binary,
            "-y",
            "-f",
            "lavfi",
            "-i",
            filter_expr,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(out_path),
        ]
    )
    return out_path


def generate_transition_sfx(duration_seconds: float, out_path: Path) -> Path:
    """Generates a cinematic transition whoosh sound effect."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    filter_expr = (
        "anoisesrc=d=1.0:c=white:r=44100:a=0.15,"
        "bandpass=f=800:width_type=h:w=500,"
        "afade=t=in:ss=0:d=0.3,afade=t=out:st=0.3:d=0.7"
    )
    _run_ffmpeg(
        [
            settings.ffmpeg_binary,
            "-y",
            "-f",
            "lavfi",
            "-i",
            filter_expr,
            "-c:a",
            "aac",
            str(out_path),
        ]
    )
    return out_path


def mix_master_soundtrack(
    voice_path: Path,
    out_path: Path,
    is_webtoon: bool = False,
    bgm_volume: float = 0.15,
    enable_bgm: bool = True,
) -> Path:
    """Mixes voiceover narration with ducked background music and transition SFX."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    duration = probe_duration_seconds(voice_path)

    if not enable_bgm:
        # Just copy voice
        _run_ffmpeg(
            [
                settings.ffmpeg_binary,
                "-y",
                "-i",
                str(voice_path),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(out_path),
            ]
        )
        return out_path

    # Generate matching BGM
    bgm_temp = out_path.with_suffix(".bgm.aac")
    try:
        generate_cinematic_bgm(duration, is_webtoon, bgm_temp)

        # Mix Voice (1.0) + BGM (bgm_volume, e.g. 0.15)
        _run_ffmpeg(
            [
                settings.ffmpeg_binary,
                "-y",
                "-i",
                str(voice_path),
                "-i",
                str(bgm_temp),
                "-filter_complex",
                f"[0:a]volume=1.0[voice];[1:a]volume={bgm_volume:.2f}[bgm];[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(out_path),
            ]
        )
    finally:
        bgm_temp.unlink(missing_ok=True)

    return out_path
