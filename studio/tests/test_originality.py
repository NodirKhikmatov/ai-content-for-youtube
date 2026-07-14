"""Originality & Angle agent test — mocks embed_text so this runs without
VOYAGE_API_KEY. Covers: no similar prior angle (passes), a near-identical
prior angle (flagged for human review), and an embedding failure (also
flagged for human review, not propagated as an exception — see the
"not allowed to fail open" rule in originality.py's module docstring).
"""

import random
from uuid import uuid4

import pytest

from studio import db
from studio.agents import originality


def _make_video(channel_id, suffix=""):
    title = f"Test Case {uuid4()}{suffix}"
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
    return case, video_id


@pytest.fixture
def channel_id():
    return db.get_channel_id("The Turning Point")


@pytest.fixture
def seeded_video(channel_id):
    case, video_id = _make_video(channel_id)
    return {
        "case_id": str(case["id"]),
        "video_id": str(video_id),
        "research_brief": {"thesis": "a fresh angle nobody has used", "turning_point": "tp"},
    }


def test_no_similar_angle_passes(monkeypatch, seeded_video):
    # originality.run() always records its own embedding into the shared
    # corpus, including on a passing run — a deterministic vector here would
    # collide with the row *this same test* left behind on a previous run
    # against the persistent dev DB. Random avoids that self-collision.
    fresh_vector = [random.random() for _ in range(1024)]
    monkeypatch.setattr(originality, "embed_text", lambda _text: fresh_vector)

    result = originality.run(dict(seeded_video))

    assert result["originality_verdict"]["needs_human_review"] is False


def test_near_duplicate_angle_flagged(monkeypatch, channel_id, seeded_video):
    # A constant vector like [0.5]*1024 collides with leftover rows from
    # earlier runs of this same test against the persistent dev DB (a tie at
    # similarity 1.0 resolves to *some* matching row, not necessarily this
    # run's) — random per-run values make an exact collision astronomically
    # unlikely instead.
    prior_vector = [random.random() for _ in range(1024)]
    prior_case, prior_video_id = _make_video(channel_id, "-prior")
    db.record_angle_embedding(
        channel_id, prior_video_id, prior_case["id"], "prior angle", prior_vector
    )

    monkeypatch.setattr(originality, "embed_text", lambda _text: prior_vector)

    result = originality.run(dict(seeded_video))

    verdict = result["originality_verdict"]
    assert verdict["needs_human_review"] is True
    assert verdict["top_similarity"] == pytest.approx(1.0, abs=1e-6)
    assert verdict["most_similar_video_id"] == str(prior_video_id)


def test_embedding_failure_degrades_to_human_review_not_exception(monkeypatch, seeded_video):
    def _boom(_text):
        raise RuntimeError("VOYAGE_API_KEY missing")

    monkeypatch.setattr(originality, "embed_text", _boom)

    result = originality.run(dict(seeded_video))  # must not raise

    verdict = result["originality_verdict"]
    assert verdict["needs_human_review"] is True
    assert "VOYAGE_API_KEY" in verdict["reason"]
