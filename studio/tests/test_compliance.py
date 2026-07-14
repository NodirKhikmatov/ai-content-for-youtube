"""Compliance agent test — mocks the LLM so this runs without
ANTHROPIC_API_KEY. Covers all-low-risk (approved) and one high-risk
category (rejected), and confirms every category verdict actually lands in
the `decisions` table — the audit trail this agent exists to populate, not
just an in-memory flag.
"""

from uuid import uuid4

import pytest

from studio import db
from studio.agents import compliance
from studio.agents.compliance import ComplianceResult, PolicyCategoryVerdict


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
        "script": "a narration script about a closed court case",
    }


def _mock_llm(monkeypatch, result: ComplianceResult):
    class FakeStructuredLLM:
        def invoke(self, _prompt):
            return result

    class FakeLLM:
        def with_structured_output(self, _schema):
            return FakeStructuredLLM()

    monkeypatch.setattr(compliance.settings, "anthropic_api_key", "fake-key-for-test")
    monkeypatch.setattr(compliance, "ChatAnthropic", lambda **_: FakeLLM())


def _all_low_risk() -> ComplianceResult:
    return ComplianceResult(
        verdicts=[
            PolicyCategoryVerdict(category="inauthentic_content", risk="low", rationale="original angle"),
            PolicyCategoryVerdict(category="reused_content", risk="low", rationale="original narration"),
            PolicyCategoryVerdict(category="low_value_content", risk="low", rationale="clear narrative"),
            PolicyCategoryVerdict(category="limited_ads", risk="low", rationale="closed case, public record"),
        ],
        requires_synthetic_disclosure=False,
        summary="Clean.",
    )


def _one_high_risk() -> ComplianceResult:
    return ComplianceResult(
        verdicts=[
            PolicyCategoryVerdict(category="inauthentic_content", risk="low", rationale="original angle"),
            PolicyCategoryVerdict(category="reused_content", risk="low", rationale="original narration"),
            PolicyCategoryVerdict(category="low_value_content", risk="low", rationale="clear narrative"),
            PolicyCategoryVerdict(
                category="limited_ads", risk="high", rationale="unsubstantiated allegation against a named individual"
            ),
        ],
        requires_synthetic_disclosure=False,
        summary="Limited ads risk.",
    )


def _decision_rows(video_id: str) -> list[dict]:
    with db.get_connection() as conn:
        rows = conn.execute(
            "select agent_name, decision, rationale from decisions where video_id = %s", (video_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def test_all_low_risk_approves_and_records_decisions(monkeypatch, seeded_video):
    _mock_llm(monkeypatch, _all_low_risk())

    result = compliance.run(dict(seeded_video))

    assert result["compliance_verdict"]["approved_for_publish"] is True
    video = db.get_video(seeded_video["video_id"])
    assert video["status"] == "approved"

    rows = _decision_rows(seeded_video["video_id"])
    assert len(rows) == 4
    assert all(r["agent_name"] == "compliance" for r in rows)
    assert any(r["decision"] == "inauthentic_content:low" for r in rows)


def test_one_high_risk_category_blocks_approval(monkeypatch, seeded_video):
    _mock_llm(monkeypatch, _one_high_risk())

    result = compliance.run(dict(seeded_video))

    assert result["compliance_verdict"]["approved_for_publish"] is False
    video = db.get_video(seeded_video["video_id"])
    assert video["status"] == "rejected"

    rows = _decision_rows(seeded_video["video_id"])
    assert any(r["decision"] == "limited_ads:high" for r in rows)
