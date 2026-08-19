"""AI Content Calendar Agent.

Generates a 30-day YouTube content calendar tailored to the channel's
niche and format thesis, with trending topic analysis, viral potential
scoring, and optimal publication schedule.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from studio.llm import call_llm


def generate_content_calendar(
    channel_niche: str,
    format_thesis: str,
    channel_name: str = "The Turning Point",
    days: int = 30,
    existing_cases: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Generate a 30-day AI content calendar with viral potential scoring."""

    today = date.today()
    existing_str = "\n".join(f"- {t}" for t in (existing_cases or []))

    system = f"""You are a top-tier YouTube channel strategist and content calendar expert.
You specialize in high-retention documentary and storytelling channels.
You create data-driven viral content calendars that maximize channel growth."""

    prompt = f"""Create a 30-day YouTube content calendar for:

Channel: {channel_name}
Niche: {channel_niche}
Format: {format_thesis}
Start Date: {today.isoformat()}

{f"Already produced (avoid duplicating):\\n{existing_str}" if existing_str else ""}

Generate exactly 30 video ideas spread across 30 days (one per day).
For each video, provide a JSON object with:
- "day": 1-30 (integer)
- "date": ISO date string (YYYY-MM-DD)
- "title": Viral YouTube title (max 70 chars, high-CTR, emotionally compelling)
- "hook": One-sentence viewer hook (why they MUST watch this)
- "turning_point": The pivotal moment / biggest twist in the story
- "estimated_views_potential": "viral" | "high" | "medium" | "steady"
- "content_type": "documentary" | "case_study" | "mystery" | "drama" | "educational"
- "duration_minutes": estimated video length (8-20 minutes)
- "tags": list of 5 YouTube tags (strings)
- "priority": "must_make" | "high" | "normal"

Distribute content types naturally. Front-load the first 7 days with "must_make" and "viral" potential videos to maximize early growth.

Return ONLY a JSON array of 30 objects, no other text."""

    response = call_llm(system=system, prompt=prompt)

    # Parse JSON from response
    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        entries = json.loads(text.strip())
    except Exception:
        # Fallback: generate synthetic calendar
        entries = _generate_fallback_calendar(channel_niche, today, days)

    # Enrich with computed fields
    for entry in entries:
        day_num = entry.get("day", 1)
        entry["date"] = (today + timedelta(days=day_num - 1)).isoformat()
        entry["status"] = "planned"  # planned | in_progress | produced | published
        entry["video_id"] = None

    return entries


def _generate_fallback_calendar(niche: str, start: date, days: int) -> list[dict[str, Any]]:
    """Deterministic fallback calendar if LLM is unavailable."""
    templates = [
        ("The {niche} Case That Changed Everything", "viral", "documentary"),
        ("What Really Happened: The Hidden Truth Behind {niche}", "high", "mystery"),
        ("The Day {niche} Nearly Collapsed — And Who Saved It", "viral", "drama"),
        ("Inside the Secret Meeting That Decided {niche}'s Fate", "medium", "documentary"),
        ("The Whistleblower Who Exposed {niche}'s Darkest Secret", "viral", "case_study"),
        ("How One Decision in {niche} Changed Millions of Lives", "high", "educational"),
        ("The Trial That Shocked the World: {niche} vs Justice", "viral", "drama"),
    ]
    calendar = []
    for i in range(1, days + 1):
        tmpl = templates[(i - 1) % len(templates)]
        title = tmpl[0].replace("{niche}", niche)
        calendar.append({
            "day": i,
            "date": (start + timedelta(days=i - 1)).isoformat(),
            "title": title,
            "hook": f"The untold story behind {title.lower()}.",
            "turning_point": "A single document changed everything.",
            "estimated_views_potential": tmpl[1],
            "content_type": tmpl[2],
            "duration_minutes": 12,
            "tags": [niche, "documentary", "true crime", "history", "viral"],
            "priority": "must_make" if i <= 3 else ("high" if i <= 10 else "normal"),
            "status": "planned",
            "video_id": None,
        })
    return calendar
