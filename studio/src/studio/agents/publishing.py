"""Publishing / Scheduling agent — stub. See blueprint.md Section 4.6.

YouTube only for Phase 1. Week 1's first video is published *manually*
through YouTube Studio on purpose (Section 8, Day 7) — this node stays a
no-op stub until the manual workflow has been validated once, then Day 7+
of week 2 wires it to the YouTube Data API v3.
"""

import logging

from studio.state import PipelineState

log = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    log.info("publishing: stub — manual publish only for week 1, no-op")
    return state
