"""The Phase 1 pipeline graph.

Matches blueprint.md Section 8's 12-agent Phase 1 list (13 nodes below,
including Publishing). Mostly a linear chain, with three real branches:

- Day 3: Fact Checker's hard-stop routes straight to END instead of
  continuing to Originality/Script Writer/etc.
- Day 6: Quality Review's rejection (human or auto) routes to END instead
  of Compliance.
- Day 6: Compliance's rejection routes to END instead of Publishing.

Originality's "forced human-review flag" (blueprint.md Section 4.2) is
still deliberately *not* a graph edge — it degrades gracefully (state
carries `needs_human_review`) rather than halting the run, because nothing
downstream currently consults that specific flag the way Quality Review's
human gate consults its own scores.

compiled() attaches a MemorySaver checkpointer, required for Quality
Review's interrupt()/Command(resume=...) human-in-the-loop gate to work at
all — LangGraph can't pause and later resume a run without one. It's
in-memory only: a resume must happen in the same process that paused. A
durable checkpointer is Phase 2+ work (see quality_review.py's docstring).
"""

from typing import Protocol

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from studio.agents import (
    case_sourcing,
    compliance,
    deep_research,
    fact_checker,
    originality,
    publishing,
    quality_review,
    script_writer,
    storytelling,
    subtitle,
    video_assembly,
    video_generation,
    voice_synthesis,
)
from studio.state import PipelineState


class Agent(Protocol):
    def run(self, state: PipelineState) -> PipelineState: ...


# Order matches the pipeline diagram in blueprint.md Section 4.
NODES: list[tuple[str, Agent]] = [
    ("case_sourcing", case_sourcing),
    ("deep_research", deep_research),
    ("fact_checker", fact_checker),
    ("originality", originality),
    ("storytelling", storytelling),
    ("script_writer", script_writer),
    ("voice_synthesis", voice_synthesis),
    ("video_generation", video_generation),
    ("video_assembly", video_assembly),
    ("subtitle", subtitle),
    ("quality_review", quality_review),
    ("compliance", compliance),
    ("publishing", publishing),
]


def _route_after_fact_check(state: PipelineState) -> str:
    fact_check = state.get("fact_check") or {}
    if fact_check.get("hard_stop"):
        return END
    return "originality"


def _route_after_quality_review(state: PipelineState) -> str:
    verdict = state.get("quality_verdict") or {}
    if verdict.get("decision") not in ("approve", "auto_approved"):
        return END
    return "compliance"


def _route_after_compliance(state: PipelineState) -> str:
    verdict = state.get("compliance_verdict") or {}
    if not verdict.get("approved_for_publish"):
        return END
    return "publishing"


CONDITIONAL_SOURCES = {"fact_checker", "quality_review", "compliance"}


def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    for name, agent in NODES:
        graph.add_node(name, agent.run)

    graph.add_edge(START, NODES[0][0])
    for (name, _), (next_name, _) in zip(NODES, NODES[1:]):
        if name in CONDITIONAL_SOURCES:
            continue  # wired conditionally below, not linearly
        graph.add_edge(name, next_name)

    graph.add_conditional_edges(
        "fact_checker", _route_after_fact_check, {"originality": "originality", END: END}
    )
    graph.add_conditional_edges(
        "quality_review", _route_after_quality_review, {"compliance": "compliance", END: END}
    )
    graph.add_conditional_edges(
        "compliance", _route_after_compliance, {"publishing": "publishing", END: END}
    )

    graph.add_edge(NODES[-1][0], END)

    return graph


def compiled():
    return build_graph().compile(checkpointer=InMemorySaver())
