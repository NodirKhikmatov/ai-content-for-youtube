"""Script Writer agent. See blueprint.md Section 4.3.

Turns the Storytelling beat sheet into full narration prose, then validates
the whole script's pacing against the 8-15 minute long-form target from
blueprint.md Section 2, using the same word-count-to-seconds math
Storytelling uses for the hook (studio/pacing.py) — auto-retrying once with
an explicit trim/expand instruction if it's off target, per blueprint.md's
"words-per-minute / pacing check before handoff; auto-retry with explicit
trim/expand instruction" failure-handling spec.

Humanization (varying phrasing/cadence per video so scripts don't read as
templated) is a separate agent per blueprint.md Section 4.3 and isn't built
until Phase 2 — this agent's prose is deliberately plain today, not final.
"""

import logging
from typing import cast

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

from studio import db
from studio.config import settings
from studio.pacing import seconds_for_words, word_count, words_for_seconds
from studio.state import PipelineState

log = logging.getLogger(__name__)

MODEL = "claude-opus-4-8"
TARGET_RUNTIME_SECONDS = (8 * 60, 15 * 60)  # blueprint.md Section 2: 8-15 min long-form
PACING_TOLERANCE = 0.15
MAX_PACING_RETRIES = 1


class Script(BaseModel):
    narration: str


def _prompt(case: dict, beat_sheet: dict, retry_note: str = "") -> str:
    beats_block = "\n\n".join(
        f"[{b['name'].upper()}]\n{b['content']}" for b in beat_sheet["beats"]
    )
    low = words_for_seconds(TARGET_RUNTIME_SECONDS[0])
    high = words_for_seconds(TARGET_RUNTIME_SECONDS[1])
    return (
        f'Write the full narration script for a "Turning Point" documentary '
        f"episode about \"{case['title']}\" from this beat sheet. One "
        f"continuous narration, in beat order, {low}-{high} words total "
        f"(roughly {TARGET_RUNTIME_SECONDS[0] // 60}-"
        f"{TARGET_RUNTIME_SECONDS[1] // 60} minutes spoken).\n\n"
        f"{beats_block}{retry_note}"
    )


def run(state: PipelineState) -> PipelineState:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY missing — see .env.example.")

    video_id = state["video_id"]
    case = db.get_case(state["case_id"])
    beat_sheet = state.get("beat_sheet")
    if not beat_sheet or not beat_sheet.get("beats"):
        raise RuntimeError(
            "No beat sheet in state — Storytelling must run before Script Writer."
        )

    low_bound = TARGET_RUNTIME_SECONDS[0] * (1 - PACING_TOLERANCE)
    high_bound = TARGET_RUNTIME_SECONDS[1] * (1 + PACING_TOLERANCE)

    try:
        llm = ChatAnthropic(model=MODEL, api_key=settings.anthropic_api_key, temperature=0.4)  # type: ignore[call-arg,arg-type]
        structured_llm = llm.with_structured_output(Script)

        result = cast(Script, structured_llm.invoke(_prompt(case, beat_sheet)))
        seconds = seconds_for_words(word_count(result.narration))

        retries = 0
        while not (low_bound <= seconds <= high_bound) and retries < MAX_PACING_RETRIES:
            direction = "expand" if seconds < TARGET_RUNTIME_SECONDS[0] else "trim"
            retry_note = (
                f"\n\nYour previous draft was {word_count(result.narration)} words "
                f"(~{seconds / 60:.1f} min spoken) — {direction} it to land between "
                f"{TARGET_RUNTIME_SECONDS[0] // 60} and "
                f"{TARGET_RUNTIME_SECONDS[1] // 60} minutes."
            )
            result = cast(Script, structured_llm.invoke(_prompt(case, beat_sheet, retry_note)))
            seconds = seconds_for_words(word_count(result.narration))
            retries += 1

    except Exception as exc:
        db.record_agent_run(video_id, "script_writer", "failed", error=str(exc))
        raise

    within_target = TARGET_RUNTIME_SECONDS[0] <= seconds <= TARGET_RUNTIME_SECONDS[1]

    db.update_video(video_id, status="scripted", script=result.narration)
    db.record_agent_run(
        video_id,
        "script_writer",
        "succeeded",
        input={"beat_count": len(beat_sheet["beats"])},
        output={
            "word_count": word_count(result.narration),
            "estimated_seconds": seconds,
            "within_target": within_target,
            "retries": retries,
        },
    )

    log.info(
        "script_writer: %d words (~%.1f min), within_target=%s, retries=%d",
        word_count(result.narration),
        seconds / 60,
        within_target,
        retries,
    )

    state["script"] = result.narration
    return state
