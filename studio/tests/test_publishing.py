"""Publishing agent test — pure DB logic, no external API, so this runs for
real against the dev DB. Covers the manual-publish checklist it prepares
and confirms it never claims a video is actually published (that's
mark_published.py's job, run by hand after a real upload — see
scripts/mark_published.py, verified by running it, not pytest-imported,
same as scripts/init_db.py and scripts/seed_cases.py).
"""

from uuid import uuid4

import pytest

from studio import db
from studio.agents import publishing


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
        "assembled_video_path": "/fake/final.mp4",
        "subtitle_path": "/fake/captions.srt",
        "research_brief": {"thesis": "a test thesis"},
    }


def test_prepares_manual_publish_checklist_without_claiming_published(seeded_video):
    result = publishing.run(dict(seeded_video))

    assert result["published"] is False

    video = db.get_video(seeded_video["video_id"])
    assert video["title"].startswith("The Turning Point:")
    assert video["status"] != "published"  # Publishing never sets this itself


def test_missing_assembled_video_raises(seeded_video):
    state = dict(seeded_video)
    del state["assembled_video_path"]

    with pytest.raises(RuntimeError, match="assembled_video_path"):
        publishing.run(state)
