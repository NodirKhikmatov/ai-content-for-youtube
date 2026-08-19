"""Builds the pre-populated state for resuming a video from the first
pipeline stage that hasn't actually completed — shared by
scripts/run_pipeline.py's CLI and web/app.py's dashboard, so the two don't
drift onto different ideas of what "resuming" reuses. See graph.py's
_route_from_start docstring for the routing side of this.
"""

from typing import Any

from studio import db

# State fields that a completed early stage writes, in the order
# graph.py's _route_from_start checks them — mirrors that function so
# callers' "here's what we're reusing" reporting stays honest about what
# actually gets skipped.
RESUMABLE_FIELDS: list[tuple[str, str]] = [
    ("deep_research", "research_brief"),
    ("fact_checker", "fact_check"),
    ("originality", "originality_verdict"),
    ("storytelling", "beat_sheet"),
]


def build_resume_state(video_id: str) -> dict[str, Any]:
    video = db.get_video(video_id)
    state: dict[str, Any] = {"video_id": str(video_id), "case_id": str(video["case_id"])}

    for agent_name, field in RESUMABLE_FIELDS:
        output = db.get_latest_agent_output(video_id, agent_name)
        if output is not None:
            state[field] = output

    if video.get("script"):
        state["script"] = video["script"]

    return state
