"""Originality & Angle agent — stub. See blueprint.md Section 4.2.

Modeled on YouTube's own "interchangeable content" test: checks structural
similarity against the channel's past scripts, not just topic. Not allowed
to fail open — on failure it forces a human-review flag.

Day 1: wired into the graph, passes state through unchanged.
Day 3: embedding pipeline against the (initially empty) script corpus.
"""

import logging

from studio.state import PipelineState

log = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    log.info("originality: stub — passing state through unchanged")
    return state
