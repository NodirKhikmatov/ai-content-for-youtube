"""The LangGraph pipeline state.

Every node in graph.py reads and writes a subset of this. Field names track
the pipeline stages in blueprint.md Section 4 (agent architecture) and
Section 8 (Phase 1 agent list) — one field per stage output, not per agent,
since a couple of Phase-2+ agents (Storytelling, SEO, Thumbnail...) will
read/write the same fields as their Phase-1 neighbors once they land.
"""

from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    # identity
    case_id: str
    video_id: str

    # research
    research_brief: dict[str, Any]
    fact_check: dict[str, Any]
    originality_verdict: dict[str, Any]

    # creation
    beat_sheet: dict[str, Any]
    script: str

    # production
    voice_audio_path: str
    video_clip_paths: list[str]
    assembled_video_path: str
    subtitle_path: str

    # qa / compliance
    quality_verdict: dict[str, Any]
    compliance_verdict: dict[str, Any]

    # distribution
    youtube_video_id: str
    published: bool

    # custom input / topic
    custom_topic: dict[str, Any]

    # bookkeeping
    errors: list[str]
