"""SEO & Metadata Agent.

Produces viral YouTube titles (high CTR), an optimized description with chapter
timestamps, search tags, and 3 AI thumbnail visual prompts based on the script
and story beats.
"""

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from studio import db
from studio.config import settings
from studio.state import PipelineState
from studio.tools.llm import invoke_with_retry

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-5"


class SEOMetadata(BaseModel):
    viral_titles: list[str] = Field(
        description="5 distinct, high-CTR YouTube titles (curiosity gap, emotional, dramatic).",
        min_length=3,
        max_length=5,
    )
    description: str = Field(
        description="Full YouTube description with summary hook, timestamps, and call-to-actions."
    )
    tags: list[str] = Field(
        description="15-20 relevant YouTube search tags / keywords.",
        min_length=5,
    )
    hashtags: list[str] = Field(
        description="3-5 viral hashtags (e.g. #ManhwaRecap, #Documentary, #TrueCrime).",
        min_length=3,
    )
    thumbnail_prompts: list[str] = Field(
        description="3 high-contrast 16:9 visual concept prompts for AI image generation.",
        min_length=3,
        max_length=3,
    )


def _is_webtoon(case: dict | None) -> bool:
    if not case:
        return False
    jurisdiction = (case.get("jurisdiction") or "").lower()
    return any(k in jurisdiction for k in ("webtoon", "manhwa", "manga", "anime", "recap", "comic"))


def _seo_prompt(case: dict, brief: dict, script: str) -> str:
    is_wb = _is_webtoon(case)
    genre_hint = "Webtoon / Manhwa Anime Recap" if is_wb else "Documentary & True Story"
    
    return (
        f"You are a top-tier YouTube strategist & SEO expert specializing in {genre_hint} channels.\n\n"
        f"Generate a high-converting YouTube release package for:\n"
        f"Title/Subject: {case.get('title')}\n"
        f"Niche/Genre: {case.get('jurisdiction')}\n"
        f"Turning Point/Climax: {case.get('turning_point')}\n"
        f"Script summary / sample:\n{script[:1500]}...\n\n"
        f"Package Requirements:\n"
        f"1. 5 Viral Titles: Click-worthy, suspenseful, under 70 characters. Avoid clickbait that misleads, but maximize curiosity.\n"
        f"2. Formatted Description: 3-4 sentence hook summary, chapter timestamps outline, engaging engagement question, and credits.\n"
        f"3. 15-20 Search Tags.\n"
        f"4. 3-5 Hashtags.\n"
        f"5. 3 Thumbnail Visual Prompts: 16:9 composition, dynamic lighting, high contrast, expressive protagonist/subject face, glowing effects or dramatic shadows for maximum CTR."
    )


def _offline_metadata(case: dict) -> SEOMetadata:
    is_wb = _is_webtoon(case)
    title = case.get("title", "Untitled Video")
    tp = case.get("turning_point", "")
    if is_wb:
        return SEOMetadata(
            viral_titles=[
                f"He Was The Weakest Until He Awakened Level 999: {title}",
                f"Everyone Mocked Him, But He Unlocked An SSS-Rank System | {title}",
                f"The Day The World Regretted Betraying Him... ({title})",
                f"From E-Rank To God: {title} Full Recap",
                f"They Banished Him, So He Came Back As A Monster | {title}",
            ],
            description=f"{title} Full Story Recap.\n\n{tp}\n\nTimestamps:\n0:00 - The Weakest\n1:30 - The Awakening\n4:00 - Leveling Up\n7:30 - The Final Showdown\n10:00 - Aftermath\n\n#ManhwaRecap #Anime #Webtoon",
            tags=[title, "manhwa recap", "webtoon recap", "anime recap", "system manhwa", "leveling", "solo leveling", "overpowered mc", "reincarnation manhwa"],
            hashtags=["#ManhwaRecap", "#Webtoon", "#AnimeRecap", "#SoloLeveling"],
            thumbnail_prompts=[
                f"Intense Korean manhwa hero with glowing neon blue eyes and dark aura, close up, high contrast cinematic anime lighting",
                f"Protagonist holding glowing energy blade standing over defeated monster in dark dungeon, Solo Leveling art style",
                f"Split face dramatic contrast: weak bruised human on left, glowing god-tier awakened aura on right, 8k anime art",
            ],
        )
    return SEOMetadata(
        viral_titles=[
            f"The Single Decision That Changed History: {title}",
            f"The Untold Story Behind {title} (The Turning Point)",
            f"How One Mistake Exposed The Entire Truth: {title}",
            f"What Really Happened During {title}?",
            f"The Hidden Evidence That Flipped {title}",
        ],
        description=f"A complete documentary breakdown of {title}.\n\n{tp}\n\nTimestamps:\n0:00 - Introduction\n2:00 - The Escalation\n5:30 - The Turning Point\n9:00 - The Verdict\n\n#Documentary #History #TheTurningPoint",
        tags=[title, "documentary", "history", "true crime", "the turning point", "investigation", "unsolved mysteries"],
        hashtags=["#Documentary", "#History", "#TheTurningPoint"],
        thumbnail_prompts=[
            f"Dramatic cinematic portrait with intense rim lighting, mysterious dark background, documentary aesthetic",
            f"Historical evidence file folder with glowing confidential stamp on dark mahogany desk, cinematic lighting",
            f"Split composition: key decision moment with high-contrast shadows and dramatic lens flare",
        ],
    )


def generate_seo_metadata(case: dict, brief: dict, script: str) -> SEOMetadata:
    if not settings.anthropic_api_key:
        return _offline_metadata(case)

    try:
        llm = ChatAnthropic(model=MODEL, api_key=settings.anthropic_api_key)  # type: ignore[call-arg,arg-type]
        structured_llm = llm.with_structured_output(SEOMetadata)
        return invoke_with_retry(structured_llm, _seo_prompt(case, brief, script))
    except Exception as exc:
        log.warning("LLM SEO generation failed (%s) — falling back to deterministic template", exc)
        return _offline_metadata(case)
