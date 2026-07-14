"""Quality Review agent — stub. See blueprint.md Section 4.5.

This is the MVP-stage human-in-the-loop gate (blueprint.md Friction 02):
the auto-pass threshold starts high and only loosens as the agent's
tracked false-pass rate earns it. Day 6 of week 1 is literally you,
watching the assembled cut against the rubric — this node is the seam
where that human judgment enters the graph.

Day 1: wired into the graph, passes state through unchanged.
"""

import logging

from studio.state import PipelineState

log = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    log.info("quality_review: stub — passing state through unchanged")
    return state
