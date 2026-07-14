"""Integration test: runs the real Case Sourcing agent against the local dev
Postgres (docker compose up -d; python scripts/seed_cases.py first).

No external API needed — Case Sourcing is pure DB logic — so this exercises
the actual code path, not a mock. It also actually consumes one backlog slot
(marks a case 'selected'), same as a real pipeline run would; that's
intentional, not a test-isolation gap to fix later.
"""

from studio import db
from studio.agents import case_sourcing


def test_selects_top_candidate_and_creates_video():
    channel_id = db.get_channel_id(case_sourcing.CHANNEL_NAME)
    before = db.get_top_candidate_case(channel_id)
    assert before is not None, "backlog is empty — run scripts/seed_cases.py"

    state = case_sourcing.run({})

    assert state["case_id"] == str(before["id"])
    assert "video_id" in state

    case_after = db.get_case(before["id"])
    assert case_after["status"] == "selected"

    # the next call should pick a different (lower-scored) case, not the same one
    next_candidate = db.get_top_candidate_case(channel_id)
    assert next_candidate is None or next_candidate["id"] != before["id"]
