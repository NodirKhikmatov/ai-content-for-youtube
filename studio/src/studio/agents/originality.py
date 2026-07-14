"""Originality & Angle agent. See blueprint.md Section 4.2.

blueprint.md's spec lists "draft script" as this agent's input and
"embeddings of full script structure" as its memory. That describes what
this agent becomes once a second pass runs after Script Writer — but in
*this* Phase 1 graph, Originality runs before Script Writer
(case_sourcing -> deep_research -> fact_checker -> originality ->
storytelling -> script_writer), so there is no script yet to compare.
What's actually available at this position is the research brief's thesis
and turning point, so that's what gets embedded and compared instead. This
is arguably better for Phase 1 anyway — it catches a duplicate angle before
a script-writing pass gets spent on it — but it's a deliberate resolution of
a real mismatch between the original spec's wording and the graph's actual
node order, not a coincidence.

Not allowed to fail open: unlike Fact Checker and Deep Research (which raise
and stop the pipeline on missing credentials or tool failure), a failure
here — no VOYAGE_API_KEY, an embedding call error, a DB error — degrades to
`needs_human_review = True` rather than raising. The spec's rule is "never
silently pass," not "never continue"; forcing review is the correct
response to uncertainty, a hard pipeline stop is not.
"""

import logging
from typing import Any

from studio import db
from studio.state import PipelineState
from studio.tools.embeddings import embed_text

log = logging.getLogger(__name__)

CHANNEL_NAME = "The Turning Point"
SIMILARITY_THRESHOLD = 0.90


def run(state: PipelineState) -> PipelineState:
    video_id = state["video_id"]
    case = db.get_case(state["case_id"])
    brief = state.get("research_brief", {})

    thesis = brief.get("thesis", "")
    turning_point = brief.get("turning_point") or case.get("turning_point", "")
    angle_text = f"{thesis}\n{turning_point}".strip()

    verdict: dict[str, Any]
    try:
        channel_id = db.get_channel_id(CHANNEL_NAME)
        embedding = embed_text(angle_text)

        similar = db.find_similar_angles(channel_id, embedding, limit=3)
        top = similar[0] if similar else None
        needs_review = top is not None and top["similarity"] >= SIMILARITY_THRESHOLD

        db.record_angle_embedding(channel_id, video_id, case["id"], angle_text, embedding)

        verdict = {
            "needs_human_review": needs_review,
            "top_similarity": top["similarity"] if top else None,
            "most_similar_video_id": str(top["video_id"]) if top else None,
            "reason": None,
        }
        run_status = "succeeded"

    except Exception as exc:
        log.warning("originality: failing open is not allowed — forcing human review (%s)", exc)
        verdict = {
            "needs_human_review": True,
            "top_similarity": None,
            "most_similar_video_id": None,
            "reason": f"originality check failed: {exc}",
        }
        run_status = "failed"

    db.record_agent_run(
        video_id,
        "originality",
        run_status,
        input={"case_id": state["case_id"]},
        output=verdict,
        error=verdict["reason"] if run_status == "failed" else None,
    )

    if verdict["needs_human_review"]:
        log.info(
            "originality: flagged for human review (similarity=%s vs video %s)",
            verdict["top_similarity"],
            verdict["most_similar_video_id"],
        )
    else:
        log.info("originality: passed, angle is sufficiently distinct")

    state["originality_verdict"] = verdict
    return state
