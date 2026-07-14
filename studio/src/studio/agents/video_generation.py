"""Video / Visual Generation agent — stub. See blueprint.md Section 4.4.

Vendor-agnostic interface over the video-gen backend — Kling only for
Phase 1 (cheap bulk B-roll); Veo added later for hero shots. Never hard-code
a single vendor here (Sora 2 was deprecated ~6 months after launch).

Day 1: wired into the graph, passes state through unchanged.
Day 5: real Kling B-roll generation per scene in `beat_sheet`.
"""

import logging

from studio.state import PipelineState

log = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    log.info("video_generation: stub — passing state through unchanged")
    return state
