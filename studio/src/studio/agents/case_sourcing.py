"""Case Sourcing agent.

Retargeted Trend Research agent (blueprint.md Section 4.1) for a
backlog-driven niche rather than a trending-topic one (Section 8: "closed
cases aren't trend-driven the way news is"). Doesn't decide what's a good
case — that's scripts/seed_cases.py's scoring rubric today, and will move to
CourtListener/Wikipedia-driven scoring once the manual backlog runs low.
This agent's job is narrower: take the top-scored untouched candidate,
promote it into a video record, and hand its id downstream.
"""

import logging

from studio import db
from studio.state import PipelineState

log = logging.getLogger(__name__)

CHANNEL_NAME = "The Turning Point"


def run(state: PipelineState) -> PipelineState:
    channel_id = db.get_channel_id(CHANNEL_NAME)

    custom_topic = state.get("custom_topic")
    case_id = state.get("case_id")

    if custom_topic:
        title = custom_topic.get("title", "Custom Story")
        turning_point = custom_topic.get("turning_point", "")
        jurisdiction = custom_topic.get("niche") or custom_topic.get("jurisdiction") or "Custom"
        era = custom_topic.get("era", "Modern")
        score = 99.0
        db.upsert_case(channel_id, title, jurisdiction, era, turning_point, score)
        case = db.get_case_by_title(channel_id, title)
    elif case_id:
        case = db.get_case(case_id)
    else:
        case = db.get_top_candidate_case(channel_id)

    if case is None:
        raise RuntimeError(
            "No candidate cases left in the backlog. Run scripts/seed_cases.py "
            "to add more, or raise the score of a rejected one."
        )

    db.mark_case_selected(case["id"])
    video_id = db.create_video_for_case(case["id"], channel_id, case["title"])

    db.record_agent_run(
        video_id,
        agent_name="case_sourcing",
        status="succeeded",
        input={"channel": CHANNEL_NAME, "custom": bool(custom_topic)},
        output={"case_id": str(case["id"]), "title": case["title"], "score": case["score"]},
    )

    log.info("case_sourcing: selected %r (score=%s)", case["title"], case["score"])

    state["case_id"] = str(case["id"])
    state["video_id"] = str(video_id)
    return state
