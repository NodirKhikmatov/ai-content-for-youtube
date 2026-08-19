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

from langgraph.graph import END

from studio.graph import (
    NODES,
    _route_after_compliance,
    _route_after_fact_check,
    _route_after_quality_review,
    _route_from_start,
    compiled,
)


def test_graph_compiles():
    compiled()


def test_fresh_run_starts_at_case_sourcing():
    assert _route_from_start({}) == "case_sourcing"


def test_resume_with_only_video_id_starts_at_deep_research():
    assert _route_from_start({"video_id": "x"}) == "deep_research"


def test_resume_with_research_brief_skips_to_fact_checker():
    state = {"video_id": "x", "research_brief": {"thesis": "t"}}
    assert _route_from_start(state) == "fact_checker"


def test_resume_with_fact_check_skips_to_originality():
    state = {"video_id": "x", "research_brief": {}, "fact_check": {"hard_stop": False}}
    assert _route_from_start(state) == "originality"


def test_resume_with_beat_sheet_skips_to_script_writer():
    state = {"video_id": "x", "fact_check": {}, "beat_sheet": {"beats": []}}
    assert _route_from_start(state) == "script_writer"


def test_resume_with_script_fans_out_to_voice_and_video():
    # script_writer's normal completion fans out to both voice_synthesis
    # and video_generation (LINEAR_EDGES) — resuming past it must fan out
    # the same way, or video_generation never runs and video_assembly fails
    # downstream with no clip paths in state.
    state = {"video_id": "x", "beat_sheet": {}, "script": "narration text"}
    assert _route_from_start(state) == ["voice_synthesis", "video_generation"]


def test_routes_to_originality_when_fact_check_passes():
    state = {"fact_check": {"hard_stop": False}}
    assert _route_after_fact_check(state) == "originality"


def test_routes_to_end_on_hard_stop():
    state = {"fact_check": {"hard_stop": True}}
    assert _route_after_fact_check(state) == END


def test_routes_to_originality_when_fact_check_missing():
    # defensive default: no fact_check in state should never be treated as
    # a silent pass-through hard stop
    assert _route_after_fact_check({}) == "originality"


def test_routes_to_compliance_on_auto_approve():
    assert _route_after_quality_review({"quality_verdict": {"decision": "auto_approved"}}) == "compliance"


def test_routes_to_compliance_on_human_approve():
    assert _route_after_quality_review({"quality_verdict": {"decision": "approve"}}) == "compliance"


def test_routes_to_end_on_quality_review_rejection():
    assert _route_after_quality_review({"quality_verdict": {"decision": "reject"}}) == END


def test_routes_to_end_when_quality_verdict_missing():
    # defensive default: absence of a verdict must never be treated as approval
    assert _route_after_quality_review({}) == END


def test_routes_to_publishing_on_compliance_approval():
    verdict = {"compliance_verdict": {"approved_for_publish": True}}
    assert _route_after_compliance(verdict) == "publishing"


def test_routes_to_end_on_compliance_rejection():
    verdict = {"compliance_verdict": {"approved_for_publish": False}}
    assert _route_after_compliance(verdict) == END


def test_routes_to_end_when_compliance_verdict_missing():
    assert _route_after_compliance({}) == END


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
