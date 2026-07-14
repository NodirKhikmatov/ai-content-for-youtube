"""Quality Review agent test — mocks review_video (no GEMINI_API_KEY).
Exercises the real LangGraph interrupt()/resume cycle for a below-threshold
score, not just the agent function called directly: the human gate is a
graph-level pause/resume, wrapped here in a minimal single-node graph
rather than the full 13-node pipeline (verified empirically against the
installed langgraph version first, not assumed — invoke() on a paused run
returns a dict with an "__interrupt__" key holding Interrupt objects).
"""

from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from studio import db
from studio.agents import quality_review
from studio.agents.quality_review import QualityVerdict, RubricScore
from studio.state import PipelineState


@pytest.fixture
def seeded_video():
    channel_id = db.get_channel_id("The Turning Point")
    title = f"Test Case {uuid4()}"
    db.upsert_case(
        channel_id,
        title=title,
        jurisdiction="Nowhere",
        era="2020",
        turning_point="a test fixture",
        score=1.0,
    )
    case = db.get_case_by_title(channel_id, title)
    db.mark_case_selected(case["id"])
    video_id = db.create_video_for_case(case["id"], channel_id, case["title"])
    return {
        "case_id": str(case["id"]),
        "video_id": str(video_id),
        "assembled_video_path": "/fake/video.mp4",
    }


def _quality_review_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("quality_review", quality_review.run)
    graph.add_edge(START, "quality_review")
    graph.add_edge("quality_review", END)
    return graph.compile(checkpointer=InMemorySaver())


def _high_scores() -> QualityVerdict:
    return QualityVerdict(
        scores=[
            RubricScore(dimension="pacing", score=0.97, notes="tight"),
            RubricScore(dimension="factual_consistency", score=0.98, notes="matches script"),
            RubricScore(dimension="av_sync", score=0.96, notes="clean"),
            RubricScore(dimension="brand_style", score=0.97, notes="on brand"),
        ],
        issues=[],
    )


def _low_scores() -> QualityVerdict:
    return QualityVerdict(
        scores=[
            RubricScore(dimension="pacing", score=0.6, notes="drags in the middle"),
            RubricScore(dimension="factual_consistency", score=0.9, notes="fine"),
            RubricScore(dimension="av_sync", score=0.9, notes="fine"),
            RubricScore(dimension="brand_style", score=0.9, notes="fine"),
        ],
        issues=["middle section drags"],
    )


def test_high_score_auto_approves_without_interrupting(monkeypatch, seeded_video):
    monkeypatch.setattr(quality_review.settings, "gemini_api_key", "fake-key-for-test")
    monkeypatch.setattr(quality_review, "review_video", lambda *a, **kw: _high_scores())

    app = _quality_review_graph()
    config = {"configurable": {"thread_id": str(uuid4())}}

    result = app.invoke(dict(seeded_video), config=config)

    assert "__interrupt__" not in result
    assert result["quality_verdict"]["decision"] == "auto_approved"


def test_low_score_interrupts_and_resumes_on_human_approval(monkeypatch, seeded_video):
    monkeypatch.setattr(quality_review.settings, "gemini_api_key", "fake-key-for-test")
    monkeypatch.setattr(quality_review, "review_video", lambda *a, **kw: _low_scores())

    app = _quality_review_graph()
    config = {"configurable": {"thread_id": str(uuid4())}}

    paused = app.invoke(dict(seeded_video), config=config)
    assert "__interrupt__" in paused
    payload = paused["__interrupt__"][0].value
    assert payload["issues"] == ["middle section drags"]

    resumed = app.invoke(
        Command(resume={"decision": "approve", "notes": "acceptable, ship it"}), config=config
    )

    assert resumed["quality_verdict"]["decision"] == "approve"
    video = db.get_video(seeded_video["video_id"])
    assert video["status"] != "rejected"


def test_low_score_interrupts_and_resumes_on_human_rejection(monkeypatch, seeded_video):
    monkeypatch.setattr(quality_review.settings, "gemini_api_key", "fake-key-for-test")
    monkeypatch.setattr(quality_review, "review_video", lambda *a, **kw: _low_scores())

    app = _quality_review_graph()
    config = {"configurable": {"thread_id": str(uuid4())}}

    app.invoke(dict(seeded_video), config=config)
    resumed = app.invoke(
        Command(resume={"decision": "reject", "notes": "redo pacing"}), config=config
    )

    assert resumed["quality_verdict"]["decision"] == "reject"
    video = db.get_video(seeded_video["video_id"])
    assert video["status"] == "rejected"


def test_missing_video_path_raises_without_calling_gemini(monkeypatch, seeded_video):
    monkeypatch.setattr(
        quality_review,
        "review_video",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    state = dict(seeded_video)
    del state["assembled_video_path"]

    with pytest.raises(RuntimeError, match="assembled_video_path"):
        quality_review.run(state)
