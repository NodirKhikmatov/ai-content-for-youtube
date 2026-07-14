"""Voice Synthesis agent — stub. See blueprint.md Section 4.4.

ElevenLabs primary, Fish Audio / Chatterbox fallback on vendor outage —
rotates among a licensed voice pool per channel rather than reusing one
static voice verbatim across every video.

Day 1: wired into the graph, passes state through unchanged.
Day 5: real synthesis, writes the audio track to R2 via storage.py.
"""

import logging

from studio.state import PipelineState

log = logging.getLogger(__name__)


def run(state: PipelineState) -> PipelineState:
    log.info("voice_synthesis: stub — passing state through unchanged")
    return state
