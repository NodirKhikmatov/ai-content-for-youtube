"""Storytelling / Narrative Structure agent. See blueprint.md Section 4.3
and Section 8 ("the beat sheet *is* the format's identity here").

Produces the "Turning Point" beat sheet: hook -> stakes -> escalation ->
the turning-point evidence/testimony -> verdict -> aftermath. Deliberately
decoupled from the Script Writer's prose (guidance per beat, not final
narration) so structure and copy can vary independently later.

Decision logic: the hook must speak in under 8 seconds (blueprint.md
Section 4.3, mapped from TikTok's 70%-completion retention data). That's
enforced as an actual word-count check against the beat sheet, not just a
prompt instruction — one retry with an explicit trim instruction if the
model doesn't comply the first time. A beat sheet missing one of the six
required beats is a data-integrity failure, not a soft warning: it raises,
the same "never silently proceed on bad output" rule as Deep Research and
Fact Checker.
"""

import logging
from typing import Literal, cast

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from studio import db
from studio.config import settings
from studio.pacing import seconds_for_words, word_count, words_for_seconds
from studio.state import PipelineState
from studio.tools.llm import invoke_with_retry

log = logging.getLogger(__name__)

# Sonnet, not Opus: this is structural beat-sheet formatting against a
# fixed template (hook/stakes/escalation/turning_point/verdict/aftermath),
# not the open-ended research judgment Deep Research and Fact Checker do.
# Script Writer stays on Opus below — it produces the actual viewer-facing
# narration prose, where writing quality has a direct line to retention.
MODEL = "claude-sonnet-5"
HOOK_MAX_SECONDS = 8
MAX_HOOK_RETRIES = 1

BeatName = Literal["hook", "stakes", "escalation", "turning_point", "verdict", "aftermath"]
BEAT_NAMES: tuple[BeatName, ...] = (
    "hook",
    "stakes",
    "escalation",
    "turning_point",
    "verdict",
    "aftermath",
)


class Beat(BaseModel):
    name: BeatName
    content: str = Field(
        description="Guidance for the Script Writer on what this beat covers — not final prose."
    )


class BeatSheet(BaseModel):
    beats: list[Beat]


def _is_webtoon(case: dict) -> bool:
    jurisdiction = (case.get("jurisdiction") or "").lower()
    return any(k in jurisdiction for k in ("webtoon", "manhwa", "manga", "anime", "recap", "comic"))


def _prompt(case: dict, brief: dict, retry_note: str = "") -> str:
    claims_block = "\n".join(f"- {c['claim']}" for c in brief.get("claims", []))
    if _is_webtoon(case):
        return (
            f'Design the 6-beat sheet for a viral YouTube Webtoon / Manhwa Recap episode '
            f'about "{case["title"]}" ({case["jurisdiction"]}, {case["era"]}).\n\n'
            f"Manhwa 6-Beat Format:\n"
            f"1. hook: High-octane opening teasing the protagonist's impossible dilemma or ultimate hidden power (Must speak in under {HOOK_MAX_SECONDS} seconds / roughly {words_for_seconds(HOOK_MAX_SECONDS)} words).\n"
            f"2. stakes: The protagonist's desperate reality (lowest rank, bullied, impoverished, or fatal betrayal) and the ruthless world order.\n"
            f"3. escalation: The awakening incident — receiving the mysterious system, regression, or unlocking forbidden magic/arts.\n"
            f"4. turning_point: The decisive, high-stakes battle or test where the protagonist turns the tables on their arrogant oppressors.\n"
            f"5. verdict: The shocking, overwhelming victory that stuns the crowd and cements their new legendary status.\n"
            f"6. aftermath: The cliffhanger setting up the next dungeon, higher-tier monster, or rival clan.\n\n"
            f"Premise / Thesis: {brief.get('thesis', '')}\n"
            f"Turning point / Awakening: {brief.get('turning_point') or case.get('turning_point', '')}\n"
            f"Plot points:\n{claims_block}\n\n"
            f"Return exactly one beat per stage: {', '.join(BEAT_NAMES)}. Each beat provides guidance for the scriptwriter and visual prompt generator.{retry_note}"
        )

    return (
        f'Design the beat sheet for a "Turning Point" documentary episode about '
        f"the closed case \"{case['title']}\" ({case['jurisdiction']}, {case['era']}).\n\n"
        f"Format: hook -> stakes -> escalation -> the turning-point evidence/"
        f"testimony -> verdict -> aftermath. The hook must be short enough to "
        f"speak in under {HOOK_MAX_SECONDS} seconds (roughly "
        f"{words_for_seconds(HOOK_MAX_SECONDS)} words or fewer) and must tease "
        f"the turning point without giving it away.\n\n"
        f"Thesis: {brief.get('thesis', '')}\n"
        f"Turning point: {brief.get('turning_point') or case.get('turning_point', '')}\n"
        f"Verified claims:\n{claims_block}\n\n"
        f"Return exactly one beat per stage: {', '.join(BEAT_NAMES)}. Each "
        f"beat's content is guidance for a script writer, not final narration "
        f"prose.{retry_note}"
    )


def run(state: PipelineState) -> PipelineState:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY missing — see .env.example.")

    video_id = state["video_id"]
    case = db.get_case(state["case_id"])
    brief = state.get("research_brief", {})

    try:
        llm = ChatAnthropic(model=MODEL, api_key=settings.anthropic_api_key)  # type: ignore[call-arg,arg-type]
        structured_llm = llm.with_structured_output(BeatSheet)

        sheet: BeatSheet = invoke_with_retry(structured_llm, _prompt(case, brief))
        hook = next((b for b in sheet.beats if b.name == "hook"), None)

        retries = 0
        while (
            hook is not None
            and seconds_for_words(word_count(hook.content)) > HOOK_MAX_SECONDS
            and retries < MAX_HOOK_RETRIES
        ):
            retry_note = (
                f"\n\nYour previous hook was {word_count(hook.content)} words — "
                f"too long for {HOOK_MAX_SECONDS} seconds. Cut it to "
                f"{words_for_seconds(HOOK_MAX_SECONDS)} words or fewer."
            )
            sheet = cast(
                BeatSheet, invoke_with_retry(structured_llm, _prompt(case, brief, retry_note))
            )
            hook = next((b for b in sheet.beats if b.name == "hook"), None)
            retries += 1

    except Exception as exc:
        db.record_agent_run(video_id, "storytelling", "failed", error=str(exc))
        raise

    present = {b.name for b in sheet.beats}
    missing = set(BEAT_NAMES) - present
    if missing:
        db.record_agent_run(
            video_id, "storytelling", "failed", error=f"missing beats: {sorted(missing)}"
        )
        raise RuntimeError(f"Beat sheet missing required beats: {sorted(missing)}")

    hook_seconds = seconds_for_words(word_count(hook.content)) if hook else None
    beat_sheet_dict = {
        "beats": [b.model_dump() for b in sheet.beats],
        "hook_seconds_estimate": hook_seconds,
        "hook_within_budget": hook_seconds is not None and hook_seconds <= HOOK_MAX_SECONDS,
    }

    db.record_agent_run(
        video_id,
        "storytelling",
        "succeeded",
        input={"case_id": state["case_id"]},
        output=beat_sheet_dict,
    )

    log.info(
        "storytelling: %d beats, hook=%.1fs (budget %ds, retries=%d)",
        len(sheet.beats),
        hook_seconds or -1,
        HOOK_MAX_SECONDS,
        retries,
    )

    state["beat_sheet"] = beat_sheet_dict
    return state
