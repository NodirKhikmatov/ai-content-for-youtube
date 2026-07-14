"""Fact Checker agent. See blueprint.md Section 4.2.

In this Phase 1 graph, Fact Checker runs once, against the research brief's
claims, before Script Writer exists yet. blueprint.md's spec describes a
second pass after script writing too ("runs twice... pre- and post-script");
that pass isn't wired in until a script exists to check it against, which is
Phase 2+ work once Script Writer has real logic and a second Fact Checker
edge is added to the graph.

Decision logic: any claim in the *core* claims list (not counterpoints —
those are expected to complicate the story, not doom it) that comes back
"disputed" or "unverifiable" is a hard stop. This is a real graph-level
conditional edge (see graph.py's _route_after_fact_check), not just a
returned flag nobody routes on: a hard stop goes straight to END instead of
continuing to Originality/Script Writer/etc. Search-tool failure is treated
the same as a disputed claim — never "assume true".

One consolidated verification search + one LLM call per case, not a loop
over every claim individually — keeps this affordable at MVP scale, same
pattern as Deep Research's two passes.
"""

import logging
from typing import Literal, cast

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

from studio import db
from studio.config import settings
from studio.state import PipelineState
from studio.tools.search import SearchResult, tavily_search

log = logging.getLogger(__name__)

MODEL = "claude-opus-4-8"


class ClaimVerdict(BaseModel):
    claim: str
    verdict: Literal["verified", "disputed", "unverifiable"]
    rationale: str


class FactCheckResult(BaseModel):
    verdicts: list[ClaimVerdict]


def _format_sources(results: list[SearchResult]) -> str:
    if not results:
        return "(no search results returned)"
    return "\n\n".join(f"[{r['title']}]({r['url']})\n{r['content']}" for r in results)


def _verify_prompt(case: dict, claims: list[dict], results: list[SearchResult]) -> str:
    claims_block = "\n".join(
        f"- {c['claim']} (originally cited: {c.get('source_url', 'none')})" for c in claims
    )
    return (
        f"You are independently fact-checking claims for a documentary about the "
        f"closed case \"{case['title']}\" ({case['jurisdiction']}, {case['era']}), "
        f"before a script gets written from them. Do not trust the original "
        f"citation alone — corroborate against the fresh source material below.\n\n"
        f"Claims to verify:\n{claims_block}\n\n"
        f"Fresh source material:\n{_format_sources(results)}\n\n"
        f"For each claim, return a verdict: 'verified' (corroborated by at least "
        f"one independent source here), 'disputed' (sources conflict with it), or "
        f"'unverifiable' (nothing here confirms or denies it). Be conservative — "
        f"default to 'unverifiable' rather than 'verified' when evidence is thin."
    )


def run(state: PipelineState) -> PipelineState:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY missing — see .env.example.")

    video_id = state["video_id"]
    case = db.get_case(state["case_id"])
    brief = state.get("research_brief", {})
    claims = brief.get("claims", [])

    if not claims:
        result = {
            "verdicts": [],
            "hard_stop": True,
            "hard_stop_reason": "Deep Research produced no claims to verify.",
        }
        db.update_video(video_id, status="rejected")
        db.record_agent_run(video_id, "fact_checker", "succeeded", output=result)
        log.info("fact_checker: HARD STOP — no claims to check")
        state["fact_check"] = result
        return state

    try:
        llm = ChatAnthropic(model=MODEL, api_key=settings.anthropic_api_key, temperature=0)  # type: ignore[call-arg,arg-type]
        structured_llm = llm.with_structured_output(FactCheckResult)

        results = tavily_search(f"{case['title']} facts verification")
        verdict_result = cast(
            FactCheckResult, structured_llm.invoke(_verify_prompt(case, claims, results))
        )
    except Exception as exc:
        db.record_agent_run(video_id, "fact_checker", "failed", error=str(exc))
        raise

    unresolved = [v for v in verdict_result.verdicts if v.verdict != "verified"]
    hard_stop = bool(unresolved)
    hard_stop_reason = (
        None
        if not hard_stop
        else "Unresolved claims: "
        + "; ".join(f"{v.claim!r} ({v.verdict})" for v in unresolved)
    )

    result = {
        "verdicts": [v.model_dump() for v in verdict_result.verdicts],
        "hard_stop": hard_stop,
        "hard_stop_reason": hard_stop_reason,
    }

    db.update_video(video_id, status="rejected" if hard_stop else "researched")
    db.record_agent_run(
        video_id,
        "fact_checker",
        "succeeded",
        input={"case_id": state["case_id"], "claim_count": len(claims)},
        output=result,
    )

    log.info(
        "fact_checker: %s (%d/%d claims verified)",
        "HARD STOP" if hard_stop else "passed",
        len(claims) - len(unresolved),
        len(claims),
    )

    state["fact_check"] = result
    return state
