"""Policy / Monetization Compliance agent. See blueprint.md Section 4.5,
and Section 8 (Copyright/Content-ID risk folded in here for Phase 1 rather
than deferred to Phase 3, since real names/mugshots/archival footage are
the core asset type in this niche).

The rubric below is built from YouTube's own inauthentic / reused /
low-value / limited-ads policy language (blueprint.md Section 1.1), not a
vibe check. Every category verdict is written to the `decisions` table —
the audit trail the schema has carried since Day 1 that Quality Review
started using earlier in this same Day 6 pass.

Decision logic: `approved_for_publish` is recomputed from the category
verdicts server-side (any "high" risk category blocks) rather than trusted
directly off whatever the model self-reports — the same pattern Fact
Checker used for hard_stop on Day 3. A rejection is a real graph-level
conditional edge (Compliance -> END), not just a returned flag.
"""

import logging
from typing import Literal

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

from studio import db
from studio.config import settings
from studio.state import PipelineState
from studio.tools.llm import invoke_with_retry

log = logging.getLogger(__name__)

# Sonnet, not Opus: this is a categorical policy-label task (four fixed
# risk categories against a fixed rubric), not the kind of open-ended
# judgment call Deep Research and Fact Checker's claim verification is.
# Opus everywhere was paying top-tier prices for a classification task —
# revisit if Sonnet's category calls turn out to need Opus's judgment on
# real runs, but there's no a priori reason to expect that here.
MODEL = "claude-sonnet-5"

PolicyCategory = Literal[
    "inauthentic_content", "reused_content", "low_value_content", "limited_ads"
]


class PolicyCategoryVerdict(BaseModel):
    category: PolicyCategory
    risk: Literal["low", "medium", "high"]
    rationale: str


class ComplianceResult(BaseModel):
    verdicts: list[PolicyCategoryVerdict]
    requires_synthetic_disclosure: bool
    summary: str


POLICY_RUBRIC = (
    "Assess this video against YouTube's current monetization policy "
    "categories, each rated low/medium/high risk:\n\n"
    "- inauthentic_content: is this mass-produced/templated, interchangeable "
    "with other videos, or made with minimal human editorial input?\n"
    "- reused_content: is this a low-effort repost/compilation with no "
    "added commentary or creative transformation?\n"
    "- low_value_content: does it just read off a source with no narrative "
    "or educational value, or use unedited/low-effort footage?\n"
    "- limited_ads: does it depict a real person without clear "
    "documentary/commentary framing, make any medical/financial/legal "
    "advice claims, or risk misleading viewers about a current event?\n\n"
    "Also state whether the 'Altered or synthetic content' disclosure "
    "should be toggled on — required when AI-generated visuals could be "
    "mistaken for real footage of real events.\n\n"
    "Script:\n{script}\n\n"
    "Case: {title} ({jurisdiction}, {era}) — closed case, verdict already "
    "public record."
)


def run(state: PipelineState) -> PipelineState:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY missing — see .env.example.")

    video_id = state["video_id"]
    case = db.get_case(state["case_id"])
    script = state.get("script", "")

    try:
        llm = ChatAnthropic(model=MODEL, api_key=settings.anthropic_api_key)  # type: ignore[call-arg,arg-type]
        structured_llm = llm.with_structured_output(ComplianceResult)
        prompt = POLICY_RUBRIC.format(
            script=script,
            title=case["title"],
            jurisdiction=case["jurisdiction"],
            era=case["era"],
        )
        result: ComplianceResult = invoke_with_retry(structured_llm, prompt)
    except Exception as exc:
        db.record_agent_run(video_id, "compliance", "failed", error=str(exc))
        raise

    high_risk = [v for v in result.verdicts if v.risk == "high"]
    approved = not high_risk

    for v in result.verdicts:
        db.record_decision(
            video_id,
            "compliance",
            decision=f"{v.category}:{v.risk}",
            rationale=v.rationale,
        )

    output = {
        "verdicts": [v.model_dump() for v in result.verdicts],
        "requires_synthetic_disclosure": result.requires_synthetic_disclosure,
        "approved_for_publish": approved,
        "summary": result.summary,
    }

    db.update_video(video_id, status="approved" if approved else "rejected")
    db.record_agent_run(
        video_id,
        "compliance",
        "succeeded",
        input={"case_id": state["case_id"]},
        output=output,
    )

    log.info("compliance: approved=%s (%d high-risk categories)", approved, len(high_risk))

    state["compliance_verdict"] = output
    return state
