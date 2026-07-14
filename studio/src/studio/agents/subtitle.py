"""Subtitle / Caption agent — stub. See blueprint.md Section 4.4.

WhisperX / Deepgram forced alignment. Word-error-rate check against the
source script; above threshold routes to manual correction, not
auto-publish.

Day 1: wired into the graph, passes state through unchanged.
Day 5: real forced-alignment + burned-in/soft-sub file generation.
"""

import logging

from studio.state import PipelineState

log = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    log.info("subtitle: stub — passing state through unchanged")
    return state
