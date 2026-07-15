"""Prints a per-stage status table for one video from the agent_runs audit
trail — the same thing scripts/run_pipeline.py's logging shows you live,
queryable after the fact instead of writing an ad hoc query each time.

Usage:
    python scripts/status.py <video_id>
"""

import sys

from studio import db

_MARKS = {"succeeded": "OK ", "failed": "FAIL", "running": "..."}
_MAX_ERROR_LENGTH = 160


def print_status(video_id: str) -> None:
    video = db.get_video(video_id)
    runs = db.get_agent_runs(video_id)

    print(f"video:  {video_id}")
    print(f"title:  {video.get('title') or '(untitled)'}")
    print(f"status: {video['status']}")
    print()

    if not runs:
        print("No agent runs recorded yet.")
        return

    name_width = max(len(run["agent_name"]) for run in runs)
    for run in runs:
        mark = _MARKS.get(run["status"], run["status"])
        started = run["started_at"].strftime("%H:%M:%S")
        elapsed = ""
        if run["finished_at"] is not None:
            elapsed = f" ({(run['finished_at'] - run['started_at']).total_seconds():.1f}s)"
        print(f"  [{mark}] {run['agent_name']:<{name_width}}  {started}{elapsed}")
        if run["status"] == "failed" and run.get("error"):
            error = run["error"]
            if len(error) > _MAX_ERROR_LENGTH:
                error = error[:_MAX_ERROR_LENGTH] + "..."
            print(f"        {error}")


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(1)
    print_status(sys.argv[1])


if __name__ == "__main__":
    main()
