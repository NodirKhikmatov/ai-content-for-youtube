"""Video Assembly / Editor agent — stub. See blueprint.md Section 4.4.

ffmpeg + Remotion. Enforces pacing rules from TikTok retention data — cut
frequency, no dead air over 3s, hook lands in the first 8s — even on
long-form cuts.

Day 1: wired into the graph, passes state through unchanged.
Day 5: real assembly of voice + visuals + sound design + subtitle timing.
"""

import logging

from studio.state import PipelineState

log = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    log.info("video_assembly: stub — passing state through unchanged")
    return state
