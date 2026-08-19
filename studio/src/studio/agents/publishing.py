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
from studio.agents.seo import generate_seo_metadata
from studio.state import PipelineState
from studio.tools.thumbnail import generate_video_thumbnails

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
    script = state.get("script", "")

    # Generate complete SEO package
    seo = generate_seo_metadata(case, brief, script)
    default_title = f"The Turning Point: {case['title']}"

    # Generate 3 high-impact thumbnail variations
    niche = case.get("jurisdiction", "Documentary")
    tp = case.get("turning_point", "")
    thumbnail_paths = generate_video_thumbnails(
        video_id=str(video_id),
        title=case["title"],
        niche=niche,
        turning_point=tp,
        prompts=seo.thumbnail_prompts,
    )

    checklist = {
        "video_path": assembled_video_path,
        "subtitle_path": state.get("subtitle_path"),
        "suggested_title": default_title,
        "viral_titles": seo.viral_titles,
        "suggested_description": seo.description,
        "tags": seo.tags,
        "hashtags": seo.hashtags,
        "thumbnail_paths": thumbnail_paths,
        "instructions": (
            "Upload manually via YouTube Studio. Select one of the generated thumbnails "
            "and viral titles. Once uploaded, run scripts/mark_published.py or click 'Mark Published'."
        ),
    }

    db.update_video(video_id, title=default_title)
    db.record_agent_run(
        video_id,
        "publishing",
        "succeeded",
        input={"video_id": video_id},
        output=checklist,
    )

    log.info("publishing: ready for upload with %d thumbnails & SEO package", len(thumbnail_paths))

    state["published"] = False
    return state
