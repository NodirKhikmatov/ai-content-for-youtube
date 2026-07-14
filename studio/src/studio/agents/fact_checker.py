"""Fact Checker agent — stub. See blueprint.md Section 4.2.

Runs twice in the real pipeline: pre-script (against `research_brief`) and
post-script (against `script`). A disputed/unverifiable claim tied to
medical, financial, legal advice, or real-person allegations is a hard stop.

Day 1: wired into the graph, passes state through unchanged.
Day 3: real claim-verification loop.
"""

import logging

from studio.state import PipelineState

log = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    log.info("fact_checker: stub — passing state through unchanged")
    return state
