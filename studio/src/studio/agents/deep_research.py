"""Deep Research agent. See blueprint.md Section 4.2.

Two-pass: gather claims/sources for the case, then a dedicated pass
instructed to find disconfirming evidence — the counterpoints guard against
both a one-sided narrative and the kind of unchallenged claim that becomes
a Limited-Ads / misinformation risk downstream in Compliance.

Needs ANTHROPIC_API_KEY and TAVILY_API_KEY. Fails fast and loud if either is
missing, rather than silently producing an ungrounded brief — the same
principle as Fact Checker's "never default to assume true" rule.
"""

import logging
from typing import Literal, cast

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from studio import db
from studio.config import settings
from studio.state import PipelineState
from studio.tools.search import SearchResult, tavily_search

log = logging.getLogger(__name__)

# Per blueprint.md Section 5.3's LLM routing table: Claude Opus for the
# steps where judgment quality directly protects downstream fact-checking.
MODEL = "claude-opus-4-8"

MIN_SOURCES_FOR_CONFIDENCE = 2


class SourcedClaim(BaseModel):
    claim: str
    source_url: str
    confidence: Literal["high", "medium", "low"]


class ResearchBrief(BaseModel):
    thesis: str = Field(
        description="Why this angle, why now — the specific point of view that "
        "differentiates this video from a generic retelling of the case."
    )
    turning_point: str = Field(
        description="The single verified moment, piece of evidence, or decision "
        "the video is built around."
    )
    claims: list[SourcedClaim] = Field(default_factory=list)
    counterpoints: list[SourcedClaim] = Field(
        default_factory=list,
        description="Disconfirming or complicating evidence found in the second pass.",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Facts that remain unverified or disputed and need Fact Checker attention.",
    )


def _format_sources(results: list[SearchResult]) -> str:
    if not results:
        return "(no search results returned)"
    return "\n\n".join(f"[{r['title']}]({r['url']})\n{r['content']}" for r in results)


def _gather_prompt(case: dict, results: list[SearchResult]) -> str:
    return (
        f"You are researching a closed court case for a documentary video series "
        f"called \"The Turning Point\", whose format is: each episode reconstructs "
        f"a closed case chronologically, built around the single piece of evidence, "
        f"testimony, or decision that flipped the outcome.\n\n"
        f"Case: {case['title']} ({case['jurisdiction']}, {case['era']})\n"
        f"Working hypothesis for the turning point: {case['turning_point']}\n\n"
        f"Source material:\n{_format_sources(results)}\n\n"
        f"Produce a research brief: confirm or correct the turning-point hypothesis "
        f"against the sources, list the specific claims that support it with a "
        f"source URL and a confidence level for each, and state the thesis — why "
        f"this case, why this angle, told now. Every claim must cite one of the "
        f"URLs above; do not invent sources."
    )


def _counterpoint_prompt(case: dict, brief: ResearchBrief, results: list[SearchResult]) -> str:
    return (
        f"You previously drafted this research brief for the case "
        f"\"{case['title']}\":\n\n"
        f"Thesis: {brief.thesis}\nTurning point: {brief.turning_point}\n\n"
        f"Now actively look for disconfirming or complicating evidence — "
        f"criticism of this account, disputed facts, alternative interpretations, "
        f"anything that would change how the story should be told.\n\n"
        f"Additional source material:\n{_format_sources(results)}\n\n"
        f"Return counterpoints (as sourced claims) and any open questions that "
        f"remain unresolved. If you find nothing that meaningfully complicates the "
        f"original brief, say so via open_questions rather than fabricating a "
        f"counterpoint."
    )


def run(state: PipelineState) -> PipelineState:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY missing — see .env.example.")

    video_id = state["video_id"]
    case = db.get_case(state["case_id"])

    try:
        # langchain-anthropic's stubs are stricter than its actual pydantic
        # validation: `model` and a plain-str `api_key` both work fine at
        # runtime (verified by hand), the stub just doesn't know it.
        llm = ChatAnthropic(model=MODEL, api_key=settings.anthropic_api_key, temperature=0)  # type: ignore[call-arg,arg-type]
        structured_llm = llm.with_structured_output(ResearchBrief)

        gather_results = tavily_search(f"{case['title']} case facts timeline outcome")
        # with_structured_output's stub returns dict | BaseModel generically;
        # passing a Pydantic model as the schema always yields that model.
        brief = cast(ResearchBrief, structured_llm.invoke(_gather_prompt(case, gather_results)))

        if len(gather_results) < MIN_SOURCES_FOR_CONFIDENCE:
            brief.open_questions.append(
                f"Only {len(gather_results)} source(s) found in the gather pass — "
                "treat this brief as low-confidence until Fact Checker reviews it."
            )

        counter_results = tavily_search(f"{case['title']} controversy disputed criticism")
        counter_pass = cast(
            ResearchBrief, structured_llm.invoke(_counterpoint_prompt(case, brief, counter_results))
        )
        brief.counterpoints = counter_pass.counterpoints
        brief.open_questions.extend(counter_pass.open_questions)

    except Exception as exc:
        db.record_agent_run(
            video_id, agent_name="deep_research", status="failed", error=str(exc)
        )
        raise

    db.update_video(video_id, status="researched")
    db.record_agent_run(
        video_id,
        agent_name="deep_research",
        status="succeeded",
        input={"case_id": state["case_id"]},
        output=brief.model_dump(),
    )

    log.info(
        "deep_research: brief produced for %r (%d claims, %d counterpoints)",
        case["title"],
        len(brief.claims),
        len(brief.counterpoints),
    )

    state["research_brief"] = brief.model_dump()
    return state
