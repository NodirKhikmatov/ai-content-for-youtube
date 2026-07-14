"""Runs the Phase 1 pipeline for one video, end to end, pausing for a real
human decision at Quality Review's interrupt if the auto-pass threshold
isn't met.

Needs every API key from Days 2-6 configured (Anthropic, Tavily, Voyage,
ElevenLabs, Kling, Deepgram, Gemini) to actually complete a live run.

The human-in-the-loop *interrupt* resume only works within this single
process (InMemorySaver — see graph.py's compiled() docstring): that's why
this script both starts the run AND handles its own interrupt/resume in one
continuous execution, rather than being a separate "resume later" CLI. A
durable checkpointer is Phase 2+ work, still not built here.

That's a different thing from the *stage* resume below, which this script
does support: if a video already has DB rows for early stages (research,
fact-check, storytelling, script), a crash or Ctrl-C partway through a run
no longer means starting over from Case Sourcing and re-paying for
everything that already succeeded — see graph.py's _route_from_start.

Usage:
    python scripts/run_pipeline.py                 # start a new video
    python scripts/run_pipeline.py <video_id>       # resume an existing one
"""

import logging
import subprocess
import sys
from typing import Any
from uuid import uuid4

from langgraph.types import Command

from studio import db
from studio.agents.quality_review import MIN_DIMENSION_SCORE
from studio.graph import compiled
from studio.logging_config import configure_logging

log = logging.getLogger(__name__)

# State fields that a completed early stage writes, in the order
# graph.py's _route_from_start checks them — mirrors that function so this
# script's "here's what we're reusing" printout stays honest about what
# actually gets skipped.
_RESUMABLE_FIELDS: list[tuple[str, str]] = [
    ("deep_research", "research_brief"),
    ("fact_checker", "fact_check"),
    ("originality", "originality_verdict"),
    ("storytelling", "beat_sheet"),
]


def _build_resume_state(video_id: str) -> dict[str, Any]:
    video = db.get_video(video_id)
    state: dict[str, Any] = {"video_id": str(video_id), "case_id": str(video["case_id"])}

    for agent_name, field in _RESUMABLE_FIELDS:
        output = db.get_latest_agent_output(video_id, agent_name)
        if output is not None:
            state[field] = output
            print(f"  reusing existing {field} (from {agent_name})")

    if video.get("script"):
        state["script"] = video["script"]
        print("  reusing existing script (from videos.script)")

    return state


def _open_video(path: str) -> None:
    if sys.platform == "darwin":
        try:
            subprocess.run(["open", path], check=False)
            return
        except Exception as exc:
            log.warning("Could not auto-open video: %s", exc)
    print(f"(open this manually to review: {path})")


def _print_scores(scores: dict[str, float]) -> None:
    print("Scores:")
    for dimension, score in scores.items():
        mark = "OK " if score >= MIN_DIMENSION_SCORE else "LOW"
        print(f"  [{mark}] {dimension:<20} {score:.2f}")


def _prompt_decision() -> str:
    while True:
        raw = input("Approve for Compliance review? [approve/reject]: ").strip().lower()
        if raw in ("approve", "reject"):
            return raw
        print(f"  Not understood: {raw!r}. Type exactly 'approve' or 'reject'.")


def main() -> None:
    configure_logging()

    app = compiled()
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    if len(sys.argv) > 1:
        resume_video_id = sys.argv[1]
        video = db.get_video(resume_video_id)
        if video["status"] in ("rejected", "published"):
            print(f"Video {resume_video_id} is already {video['status']} — nothing to resume.")
            return
        print(f"Resuming video {resume_video_id} (status={video['status']})")
        initial_state = _build_resume_state(resume_video_id)
    else:
        initial_state = {}

    result = app.invoke(initial_state, config=config)

    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        print(f"\n--- Quality Review needs a decision (thread {thread_id}) ---")
        video_path = payload["assembled_video_path"]
        print(f"Video: {video_path}")
        _open_video(video_path)
        _print_scores(payload["scores"])
        if payload["issues"]:
            print("Issues flagged:")
            for issue in payload["issues"]:
                print(f"  - {issue}")
        decision = _prompt_decision()
        notes = input("Notes (optional): ").strip()
        print(f"-> {decision}ing.")
        result = app.invoke(Command(resume={"decision": decision, "notes": notes}), config=config)

    print("\n--- Run finished ---")
    print(f"video: {result.get('video_id')}")
    print(f"case: {result.get('case_id')}")
    print(f"quality_verdict: {result.get('quality_verdict')}")
    print(f"compliance_verdict: {result.get('compliance_verdict')}")


if __name__ == "__main__":
    main()
