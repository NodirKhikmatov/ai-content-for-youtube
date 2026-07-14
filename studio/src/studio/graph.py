"""The Phase 1 pipeline graph.

Linear chain for now, matching blueprint.md Section 8's 12-agent Phase 1
list (13 nodes below, including Publishing). Conditional edges — Fact
Checker's hard-stop, Originality's forced human-review flag, Quality
Review's human-approval wait — are Week 1 Days 3 and 6 work, not Day 1;
wiring them onto a graph that doesn't compile yet would be premature.
"""

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

# Order matches the pipeline diagram in blueprint.md Section 4.
NODES: list[tuple[str, object]] = [
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


def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    for name, module in NODES:
        graph.add_node(name, module.run)

    graph.add_edge(START, NODES[0][0])
    for (name, _), (next_name, _) in zip(NODES, NODES[1:]):
        graph.add_edge(name, next_name)
    graph.add_edge(NODES[-1][0], END)

    return graph


def compiled():
    return build_graph().compile()
