"""Day 1 smoke test: the graph compiles and a stub-only run doesn't raise.

Not a real test of pipeline behavior — there isn't any yet. This exists so
`pytest` gives an immediate, meaningful signal the moment a Day 2+ agent
stub is filled in and breaks the wiring.
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


def test_stub_run_end_to_end():
    app = compiled()
    result = app.invoke({"case_id": "smoke-test"})
    assert result["case_id"] == "smoke-test"
