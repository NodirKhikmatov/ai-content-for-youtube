"""Publishing / Scheduling agent. See blueprint.md Section 4.6.

Deliberately does not call the YouTube Data API. blueprint.md Section 8's
Day 7 plan is explicit: "Publish video #1 manually through YouTube Studio,
not the API yet — validate the human workflow and the video itself before
automating the write path." This agent's Phase 1 job is narrower than its
eventual one: assemble the manual-publish checklist (final video path,
caption file, a title/description drawn from the research brief since
there's no SEO/Metadata agent yet — that's Phase 2) and leave the video
ready for a human to actually upload.

Video status is deliberately *not* advanced to "published" here — that
would misrepresent reality, since no upload has happened. See
scripts/mark_published.py, a separate manual confirmation step run only
after a human has actually completed the YouTube Studio upload.
"""

import logging

from studio import db
from studio.state import PipelineState

log = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    video_id = state["video_id"]
    case = db.get_case(state["case_id"])
    assembled_video_path = state.get("assembled_video_path")

    if not assembled_video_path:
        raise RuntimeError(
            "No assembled_video_path in state — Compliance must run before Publishing."
        )

    brief = state.get("research_brief", {})
    title = f"The Turning Point: {case['title']}"
    description = (
        f"{brief.get('thesis', '')}\n\n"
        f"A closed-case documentary reconstruction. {case['title']} "
        f"({case['jurisdiction']}, {case['era']})."
    ).strip()

    checklist = {
        "video_path": assembled_video_path,
        "subtitle_path": state.get("subtitle_path"),
        "suggested_title": title,
        "suggested_description": description,
        "instructions": (
            "Upload manually via YouTube Studio. Do not use the Data API yet — "
            "see blueprint.md Section 8, Day 7. Once uploaded, run "
            "scripts/mark_published.py to record it."
        ),
    }

    db.update_video(video_id, title=title)
    db.record_agent_run(
        video_id,
        "publishing",
        "succeeded",
        input={"video_id": video_id},
        output=checklist,
    )

    log.info("publishing: ready for manual upload — %s", assembled_video_path)

    state["published"] = False
    return state
