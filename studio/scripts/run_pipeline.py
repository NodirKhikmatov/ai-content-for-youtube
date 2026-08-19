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

Quality Review's decision itself goes through Telegram instead of the
terminal whenever TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID are both set (see
tools/telegram.py) — so you don't have to be sitting at this terminal
when a run pauses for review. Falls back to the terminal prompt if
Telegram isn't configured, or if it times out waiting for a reply.

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
from studio.resume import RESUMABLE_FIELDS, build_resume_state
from studio.tools import telegram

log = logging.getLogger(__name__)


def _build_resume_state(video_id: str) -> dict[str, Any]:
    """Same as studio.resume.build_resume_state, plus this CLI's own
    "here's what we're reusing" printout."""
    video = db.get_video(video_id)
    for agent_name, field in RESUMABLE_FIELDS:
        if db.get_latest_agent_output(video_id, agent_name) is not None:
            print(f"  reusing existing {field} (from {agent_name})")
    if video.get("script"):
        print("  reusing existing script (from videos.script)")
    return build_resume_state(video_id)


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


def _format_review_message(payload: dict[str, Any]) -> str:
    lines = ["Quality Review needs a decision.", "", "Scores:"]
    for dimension, score in payload["scores"].items():
        mark = "OK" if score >= MIN_DIMENSION_SCORE else "LOW"
        lines.append(f"  [{mark}] {dimension}: {score:.2f}")
    if payload["issues"]:
        lines.append("")
        lines.append("Issues flagged:")
        lines.extend(f"  - {issue}" for issue in payload["issues"])
    return "\n".join(lines)


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
        _print_scores(payload["scores"])
        if payload["issues"]:
            print("Issues flagged:")
            for issue in payload["issues"]:
                print(f"  - {issue}")

        decision: str | None = None
        notes = ""
        if telegram.is_configured():
            print("(sent to Telegram for review — reply there, or Ctrl+C to use this terminal instead)")
            message = _format_review_message(payload)
            if not telegram.send_video_if_small_enough(video_path, message):
                telegram.send_message(message)
            try:
                decision = telegram.ask_for_decision("Approve for Compliance review?")
                print(f"Telegram reply received: {decision}")
            except TimeoutError as exc:
                print(f"{exc}")

        if decision is None:
            _open_video(video_path)
            decision = _prompt_decision()
            notes = input("Notes (optional): ").strip()

        print(f"-> {'approving' if decision == 'approve' else 'rejecting'}.")
        result = app.invoke(Command(resume={"decision": decision, "notes": notes}), config=config)

    print("\n--- Run finished ---")
    print(f"video: {result.get('video_id')}")
    print(f"case: {result.get('case_id')}")
    print(f"quality_verdict: {result.get('quality_verdict')}")
    print(f"compliance_verdict: {result.get('compliance_verdict')}")


if __name__ == "__main__":
    main()
