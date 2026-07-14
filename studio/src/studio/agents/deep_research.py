"""Deep Research agent — stub. See blueprint.md Section 4.2.

Day 1: wired into the graph, passes state through unchanged.
Day 2: two-pass research (gather, then dedicated disconfirming-evidence
pass) producing the structured `research_brief`.
"""

import logging

from studio.state import PipelineState

log = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    log.info("deep_research: stub — passing state through unchanged")
    return state
