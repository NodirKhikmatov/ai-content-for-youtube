"""Quality Review agent. See blueprint.md Section 4.5.

LLM-as-judge via Gemini's native video understanding, scored against a
rubric (pacing, factual consistency with the script, visual/audio sync,
brand style). This is the MVP-stage human-in-the-loop gate (blueprint.md
Section 4.5): the auto-pass threshold starts very high on purpose — only a
near-perfect score skips human review, and it's only meant to loosen once
Analytics/Learning (Phase 2+) can show this agent's auto-pass calls
actually held up. Nothing loosens it yet.

The human gate is a real LangGraph interrupt(), not a returned flag nobody
routes on: this node actually pauses execution (via the MemorySaver
checkpointer configured in graph.py) and waits for a human decision,
resumed via scripts/run_pipeline.py's Command(resume=...). There is no code
path that silently skips this for a below-threshold video.

MemorySaver is in-memory — a resume only works within the same process that
paused. A durable checkpointer (e.g. Postgres-backed) is the natural
upgrade once this needs to survive a restart, which is exactly the kind of
thing Temporal was scoped for in blueprint.md's roadmap (Phase 2+), not
Phase 1.
"""

import logging
from typing import Literal, cast

from langgraph.types import interrupt
from pydantic import BaseModel, Field

from studio import db
from studio.config import settings
from studio.state import PipelineState
from studio.tools.video_review import review_video

log = logging.getLogger(__name__)

AUTO_PASS_THRESHOLD = 0.95
MIN_DIMENSION_SCORE = 0.85

RubricDimension = Literal["pacing", "factual_consistency", "av_sync", "brand_style"]


class RubricScore(BaseModel):
    dimension: RubricDimension
    score: float = Field(ge=0, le=1)
    notes: str


class QualityVerdict(BaseModel):
    scores: list[RubricScore]
    issues: list[str] = Field(default_factory=list)


PROMPT = (
    'Review this assembled documentary video for "The Turning Point" '
    "against four dimensions, each scored 0-1:\n"
    "- pacing: does the hook land quickly, is there dead air, does it drag?\n"
    "- factual_consistency: does the narration match the script's claims "
    "with no visual contradictions?\n"
    "- av_sync: are captions/visuals reasonably in sync with the narration?\n"
    "- brand_style: is this recognizably a coherent documentary episode, "
    "not a disjointed clip reel?\n"
    "List any specific issues you noticed, even minor ones."
)


def run(state: PipelineState) -> PipelineState:
    video_id = state["video_id"]
    assembled_video_path = state.get("assembled_video_path")
    if not assembled_video_path:
        raise RuntimeError(
            "No assembled_video_path in state — Subtitle must run before Quality Review."
        )
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY missing — see .env.example.")

    try:
        verdict = cast(
            QualityVerdict, review_video(assembled_video_path, PROMPT, QualityVerdict)
        )
    except Exception as exc:
        db.record_agent_run(video_id, "quality_review", "failed", error=str(exc))
        raise

    scores_by_dim = {s.dimension: s.score for s in verdict.scores}
    average_score = sum(scores_by_dim.values()) / len(scores_by_dim) if scores_by_dim else 0.0
    min_score = min(scores_by_dim.values()) if scores_by_dim else 0.0
    auto_pass = average_score >= AUTO_PASS_THRESHOLD and min_score >= MIN_DIMENSION_SCORE

    if auto_pass:
        decision = "auto_approved"
        rationale = (
            f"avg={average_score:.2f}, min={min_score:.2f} both clear the "
            f"auto-pass thresholds ({AUTO_PASS_THRESHOLD}/{MIN_DIMENSION_SCORE})"
        )
    else:
        human = interrupt(
            {
                "video_id": video_id,
                "assembled_video_path": assembled_video_path,
                "scores": scores_by_dim,
                "issues": verdict.issues,
                "question": "Approve this video for Compliance review?",
            }
        )
        decision = human.get("decision", "reject")
        rationale = human.get("notes") or "human review, no notes given"

    output = {
        "scores": scores_by_dim,
        "issues": verdict.issues,
        "average_score": average_score,
        "min_score": min_score,
        "auto_pass_eligible": auto_pass,
        "decision": decision,
    }

    db.record_agent_run(
        video_id,
        "quality_review",
        "succeeded",
        input={"video_path": assembled_video_path},
        output=output,
    )
    db.record_decision(video_id, "quality_review", decision, rationale, confidence=average_score)
    # Compliance is the final gate (blueprint.md 4.5) — passing Quality
    # Review doesn't mean "approved for publish" yet, so status stays
    # in_review rather than jumping to approved. Only a rejection here is
    # final; it stops the pipeline (see graph.py's routing).
    approved = decision in ("approve", "auto_approved")
    if not approved:
        db.update_video(video_id, status="rejected")

    log.info(
        "quality_review: decision=%s (auto_pass=%s, avg=%.2f)", decision, auto_pass, average_score
    )

    state["quality_verdict"] = output
    return state
