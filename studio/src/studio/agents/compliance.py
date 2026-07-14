"""Policy / Monetization Compliance agent — stub. See blueprint.md
Section 4.5 and Section 8 (Copyright/Content-ID folded in here for Phase 1).

The prompt this eventually runs is built from YouTube's own inauthentic /
reused / low-value / limited-ads policy language as a structured rubric,
plus a real-person-likeness and archival-footage licensing checklist —
both are load-bearing for this specific niche (Section 8: "real names,
mugshots, and archival news footage are the core asset type").

Every verdict this agent produces should be written to the `decisions`
table (see db/schema.sql) — that log is the audit trail if a channel is
ever flagged or appealed.

Day 1: wired into the graph, passes state through unchanged.
"""

import logging

from studio.state import PipelineState

log = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    log.info("compliance: stub — passing state through unchanged")
    return state
