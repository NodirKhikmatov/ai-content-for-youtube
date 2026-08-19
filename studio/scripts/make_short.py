"""Produces a YouTube Shorts cut (vertical, ~45-60s) from a video that has
already been through Storytelling — reuses that video's beat sheet rather
than re-running Deep Research/Fact Checker from scratch. See
studio.shorts.make_short_video's module docstring for the actual assembly
logic (shared with web/runner.py's dashboard) and
agents/shorts_script.py's for why the short's narration is its own
hook-first prose, not a truncation of the long-form script.

Deliberately outside graph.py's LangGraph pipeline: a Phase 1.5 repurposing
step, not part of the Phase 1 case->publish flow, the same "separate,
deliberately manual step" scoping as scripts/mark_published.py.

Uses the same VIDEO_GEN_BACKEND/VOICE_BACKEND/TRANSCRIBE_BACKEND settings
as the main pipeline (see .env.example) — set them to "fake" to produce a
short for free, same as scripts/run_pipeline.py.

Usage:
    python scripts/make_short.py <video_id>
"""

import sys

from studio.logging_config import configure_logging
from studio.shorts import make_short_video


def main() -> None:
    configure_logging()
    if len(sys.argv) < 2:
        print("Usage: python scripts/make_short.py <video_id>")
        sys.exit(1)

    output = make_short_video(sys.argv[1])
    print(f"\nShort ready: {output['final_path']}")
    print(f"Duration: {output['narration_seconds']:.1f}s")


if __name__ == "__main__":
    main()
