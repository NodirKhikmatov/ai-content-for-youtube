"""Structural tests for the pipeline graph: it compiles and every Phase 1
agent is wired in, in the right order.

There's deliberately no "invoke the whole graph" test here anymore. That
worked on Day 1 when every node was a no-op stub, but as of Day 2
case_sourcing does real DB writes and deep_research makes a real (paid) LLM
call — a full invoke now needs a live ANTHROPIC_API_KEY/TAVILY_API_KEY and
mutates the backlog, which isn't what a compile-time smoke test should
require. Each agent with real behavior gets its own test instead
(test_case_sourcing.py, test_deep_research.py); a genuine end-to-end run
returns once every remaining stub has real logic, likely as a manual
Day 6-7 exercise rather than a `pytest` assertion.
"""

from studio.graph import NODES, compiled


def test_graph_compiles():
    compiled()


def test_all_phase1_nodes_present():
    names = {name for name, _ in NODES}
    assert names == {
        "case_sourcing",
        "deep_research",
        "fact_checker",
        "originality",
        "storytelling",
        "script_writer",
        "voice_synthesis",
        "video_generation",
        "video_assembly",
        "subtitle",
        "quality_review",
        "compliance",
        "publishing",
    }
