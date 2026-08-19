"""Shorts Script agent — condenses an already-produced case's beat sheet
into a ~45-60 second vertical-format narration for YouTube Shorts.
blueprint.md Section 7's roadmap defers "TikTok repurposing" broadly; this
is the narrower slice of that: reusing research already paid for (Deep
Research, Fact Checker, Storytelling) rather than re-researching, the same
way Script Writer reuses Storytelling's beat sheet for the long-form cut.

Deliberately its own short prose, not a truncation of the long-form
script: a Short needs its own hook-first pacing (a viewer decides whether
to keep watching in the first couple of seconds) rather than a
proportionally-scaled-down version of a narrative paced for 8-15 minutes.

Not wired into graph.py — this runs against a video that has already been
through Storytelling (see scripts/make_short.py), the same "separate,
deliberately manual step" scoping as scripts/mark_published.py, not a node
in the Phase 1 case->publish pipeline.
"""

import logging

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

from studio import db
from studio.config import settings
from studio.pacing import seconds_for_words, word_count, words_for_seconds
from studio.tools.llm import invoke_with_retry

log = logging.getLogger(__name__)

# Same model as Script Writer: this is viewer-facing narration prose, not
# structural formatting — worth the stronger model.
MODEL = "claude-opus-4-8"
TARGET_RUNTIME_SECONDS = (45, 60)
PACING_TOLERANCE = 0.15
MAX_PACING_RETRIES = 1


class ShortScript(BaseModel):
    narration: str


def _prompt(case: dict, beat_sheet: dict, retry_note: str = "") -> str:
    beats_block = "\n\n".join(
        f"[{b['name'].upper()}]\n{b['content']}" for b in beat_sheet["beats"]
    )
    low = words_for_seconds(TARGET_RUNTIME_SECONDS[0])
    high = words_for_seconds(TARGET_RUNTIME_SECONDS[1])
    return (
        f'Write a YouTube Shorts narration for "The Turning Point" '
        f"documentary series, teasing the case \"{case['title']}\" from this "
        f"beat sheet. One continuous narration, {low}-{high} words total "
        f"(roughly {TARGET_RUNTIME_SECONDS[0]}-{TARGET_RUNTIME_SECONDS[1]} "
        f"seconds spoken).\n\n"
        f"This is NOT a compressed retelling of the whole story — it's a "
        f"vertical-video hook: open with the single most arresting line "
        f"(a Short lives or dies in its first two seconds), tease the "
        f"turning point without fully resolving it, and end on a line that "
        f"makes someone want to find the full episode.\n\n"
        f"{beats_block}{retry_note}"
    )


def run(video_id: str, case_id: str, beat_sheet: dict) -> str:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY missing — see .env.example.")

    case = db.get_case(case_id)
    if not beat_sheet or not beat_sheet.get("beats"):
        raise RuntimeError(
            "No beat sheet — Storytelling must have already run for this video."
        )

    low_bound = TARGET_RUNTIME_SECONDS[0] * (1 - PACING_TOLERANCE)
    high_bound = TARGET_RUNTIME_SECONDS[1] * (1 + PACING_TOLERANCE)

    try:
        llm = ChatAnthropic(model=MODEL, api_key=settings.anthropic_api_key)  # type: ignore[call-arg,arg-type]
        structured_llm = llm.with_structured_output(ShortScript)

        result: ShortScript = invoke_with_retry(structured_llm, _prompt(case, beat_sheet))
        seconds = seconds_for_words(word_count(result.narration))

        retries = 0
        while not (low_bound <= seconds <= high_bound) and retries < MAX_PACING_RETRIES:
            direction = "expand" if seconds < TARGET_RUNTIME_SECONDS[0] else "trim"
            retry_note = (
                f"\n\nYour previous draft was {word_count(result.narration)} words "
                f"(~{seconds:.0f}s spoken) — {direction} it to land between "
                f"{TARGET_RUNTIME_SECONDS[0]} and {TARGET_RUNTIME_SECONDS[1]} seconds."
            )
            result = invoke_with_retry(structured_llm, _prompt(case, beat_sheet, retry_note))
            seconds = seconds_for_words(word_count(result.narration))
            retries += 1
    except Exception as exc:
        db.record_agent_run(video_id, "shorts_script", "failed", error=str(exc))
        raise

    within_target = TARGET_RUNTIME_SECONDS[0] <= seconds <= TARGET_RUNTIME_SECONDS[1]
    db.record_agent_run(
        video_id,
        "shorts_script",
        "succeeded",
        input={"beat_count": len(beat_sheet["beats"])},
        output={
            "narration": result.narration,
            "word_count": word_count(result.narration),
            "estimated_seconds": seconds,
            "within_target": within_target,
            "retries": retries,
        },
    )

    log.info(
        "shorts_script: %d words (~%.0fs), within_target=%s, retries=%d",
        word_count(result.narration),
        seconds,
        within_target,
        retries,
    )

    return result.narration
