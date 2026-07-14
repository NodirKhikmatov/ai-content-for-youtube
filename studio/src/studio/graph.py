"""The Phase 1 pipeline graph.

Matches blueprint.md Section 8's 12-agent Phase 1 list (13 nodes below,
including Publishing). Mostly a linear chain, with one real branch as of
Day 3: Fact Checker's hard-stop routes straight to END instead of
continuing to Originality/Script Writer/etc — see _route_after_fact_check.

Originality's "forced human-review flag" (blueprint.md Section 4.2) is
deliberately *not* a graph edge here — it degrades gracefully (state carries
`needs_human_review`) rather than halting the run, because there's no
Quality Review gate downstream yet for it to route into. That gate, and the
human-approval wait it implies, is Day 6 work.
"""

from typing import Protocol

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


def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    for name, agent in NODES:
        graph.add_node(name, agent.run)

    graph.add_edge(START, NODES[0][0])
    for (name, _), (next_name, _) in zip(NODES, NODES[1:]):
        if name == "fact_checker":
            continue  # wired conditionally below, not linearly
        graph.add_edge(name, next_name)

    graph.add_conditional_edges(
        "fact_checker", _route_after_fact_check, {"originality": "originality", END: END}
    )

    graph.add_edge(NODES[-1][0], END)

    return graph


def compiled():
    return build_graph().compile()
