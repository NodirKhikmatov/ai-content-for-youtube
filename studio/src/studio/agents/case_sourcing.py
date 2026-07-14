"""Case Sourcing agent — stub.

Retargeted Trend Research agent (blueprint.md Section 4.1) for a
backlog-driven niche rather than a trending-topic one (Section 8: "closed
cases aren't trend-driven the way news is").

Day 1: wired into the graph, passes state through unchanged.
Day 2: CourtListener / public-record + Wikipedia backlog scoring.
"""

import logging

from studio.state import PipelineState

log = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    log.info("case_sourcing: stub — passing state through unchanged")
    return state
