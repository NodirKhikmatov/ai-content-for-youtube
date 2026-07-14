"""Script Writer agent — stub. See blueprint.md Section 4.3.

Day 1: wired into the graph, passes state through unchanged.
Day 4: full narration script from `beat_sheet` + `research_brief`, with a
words-per-minute / pacing validation pass before handoff.
"""

import logging

from studio.state import PipelineState

log = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    log.info("script_writer: stub — passing state through unchanged")
    return state
