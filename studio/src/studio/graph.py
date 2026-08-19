"""The Phase 1 pipeline graph.

Matches blueprint.md Section 8's 12-agent Phase 1 list (13 nodes below,
including Publishing). Mostly a linear chain, with two kinds of branch:

- Three hard-stop gates, each a real conditional edge to END rather than a
  flag nobody routes on: Fact Checker (Day 3), Quality Review and
  Compliance (Day 6).
- One fork/join: Voice Synthesis and Video Generation both depend only on
  Script Writer's output (the script, the beat sheet) and not on each
  other, so they run concurrently and converge at Video Assembly.
  LangGraph's Pregel executor runs nodes with satisfied dependencies in the
  same superstep by default — this needed no new infrastructure, just
  wiring two edges out of script_writer and two edges into video_assembly
  instead of one linear chain through both.

Originality's "forced human-review flag" (blueprint.md Section 4.2) is
still deliberately *not* a graph edge — it degrades gracefully (state
carries `needs_human_review`) rather than halting the run, because nothing
downstream currently consults that specific flag the way Quality Review's
human gate consults its own scores.

Resume support (`_route_from_start`): a conditional edge out of START,
same mechanism LangGraph already uses for the three hard-stop gates above,
now used the other direction — routing *past* early nodes when the state
passed into `compiled().invoke(...)` was pre-populated from the DB by
scripts/run_pipeline.py's resume path, rather than starting fresh. This
only covers case_sourcing through script_writer: everything from Voice
Synthesis onward writes a local file, and skipping those safely would need
verifying the file is still on disk, not just that a DB row says it
succeeded — left out of this pass, noted in the review as a follow-up
rather than silently expanded into.

compiled() attaches a MemorySaver checkpointer, required for Quality
Review's interrupt()/Command(resume=...) human-in-the-loop gate to work at
all — LangGraph can't pause and later resume a run without one. It's
in-memory only: a resume must happen in the same process that paused. A
durable checkpointer is Phase 2+ work (see quality_review.py's docstring).
This is unrelated to the DB-backed resume above — that one skips
*already-finished* nodes on a fresh process invocation; this one is about
resuming a *paused* interrupt within one still-running process. Different
problems, not two overlapping fixes for the same thing.
"""

import logging
import time
from typing import Protocol

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphBubbleUp
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

log = logging.getLogger(__name__)


class Agent(Protocol):
    def run(self, state: PipelineState) -> PipelineState: ...


# Order matches the pipeline diagram in blueprint.md Section 4. Order here
# no longer implies a linear chain (see LINEAR_EDGES below) — it's just the
# iteration order for graph.add_node().
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

# Direct edges only — excludes the three conditional-source nodes
# (fact_checker, quality_review, compliance), wired separately below, and
# excludes START, wired via _route_from_start. The fork (script_writer ->
# both voice_synthesis and video_generation) and join (both -> video_
# assembly) are just two edges each instead of one — no special API.
LINEAR_EDGES: list[tuple[str, str]] = [
    ("case_sourcing", "deep_research"),
    ("deep_research", "fact_checker"),
    ("originality", "storytelling"),
    ("storytelling", "script_writer"),
    ("script_writer", "voice_synthesis"),
    ("script_writer", "video_generation"),
    ("voice_synthesis", "video_assembly"),
    ("video_generation", "video_assembly"),
    ("video_assembly", "subtitle"),
    ("subtitle", "quality_review"),
]


def _route_from_start(state: PipelineState) -> str | list[str]:
    """Fresh run (no video_id yet) starts at case_sourcing as always.
    A resumed run (state pre-populated from the DB — see
    scripts/run_pipeline.py) enters at the first stage that hasn't
    succeeded yet, reusing whatever the DB already has instead of
    re-running it.

    script_writer's normal completion fans out to both voice_synthesis and
    video_generation (LINEAR_EDGES above) — routing past script_writer on
    resume has to fan out to both too, or video_generation silently never
    runs and video_assembly fails downstream with no clip paths in state."""
    if state.get("video_id") is None:
        return "case_sourcing"
    if state.get("script") is not None:
        return ["voice_synthesis", "video_generation"]
    if state.get("beat_sheet") is not None:
        return "script_writer"
    if state.get("fact_check") is not None:
        return "originality"
    if state.get("research_brief") is not None:
        return "fact_checker"
    return "deep_research"


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


def _timed(name: str, agent: Agent) -> Agent:
    """Wraps a node so every run logs when it starts, how long it took, and
    whether it succeeded or failed — once, here, rather than duplicating
    timing/logging boilerplate into all thirteen agent files."""

    class _Timed:
        def run(self, state: PipelineState) -> PipelineState:
            log.info("%s: starting", name)
            start = time.monotonic()
            try:
                result = agent.run(state)
            except GraphBubbleUp:
                # LangGraph's own control-flow signal — quality_review's
                # interrupt() raises GraphInterrupt (a GraphBubbleUp
                # subclass) to pause the graph for human review, which
                # *is* an Exception and would otherwise be caught by the
                # `except Exception` below and logged as a failure. It
                # isn't one: human review is the expected, common path
                # given how strict AUTO_PASS_THRESHOLD is. Must re-raise
                # completely unmodified (bare `raise`, no wrapping) for
                # LangGraph's runtime to actually pause/resume on it.
                elapsed = time.monotonic() - start
                log.info("%s: PAUSED after %.1fs — waiting for human review", name, elapsed)
                raise
            except Exception:
                elapsed = time.monotonic() - start
                log.error("%s: FAILED after %.1fs", name, elapsed)
                raise
            elapsed = time.monotonic() - start
            log.info("%s: succeeded in %.1fs", name, elapsed)
            return result

    return _Timed()


def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    for name, agent in NODES:
        graph.add_node(name, _timed(name, agent).run)

    graph.add_conditional_edges(
        START,
        _route_from_start,
        {
            "case_sourcing": "case_sourcing",
            "deep_research": "deep_research",
            "fact_checker": "fact_checker",
            "originality": "originality",
            "script_writer": "script_writer",
            "voice_synthesis": "voice_synthesis",
            "video_generation": "video_generation",
        },
    )

    for src, dst in LINEAR_EDGES:
        graph.add_edge(src, dst)

    graph.add_conditional_edges(
        "fact_checker", _route_after_fact_check, {"originality": "originality", END: END}
    )
    graph.add_conditional_edges(
        "quality_review", _route_after_quality_review, {"compliance": "compliance", END: END}
    )
    graph.add_conditional_edges(
        "compliance", _route_after_compliance, {"publishing": "publishing", END: END}
    )

    graph.add_edge("publishing", END)

    return graph


def compiled():
    return build_graph().compile(checkpointer=InMemorySaver())
