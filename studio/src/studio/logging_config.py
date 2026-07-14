"""Global logging setup for the pipeline's CLI entry points.

Nothing in this codebase previously called `logging.basicConfig()` (or
configured a handler any other way), so every `log.info(...)` call in every
agent — the per-run summaries this project already relies on for
debugging — was silently swallowed by Python's default root logger, which
sits at WARNING. Verified directly: a bare `log.info(...)` against a
freshly imported agent module produced no output at all. This module is
the fix, called once from each script's entry point, not at import time.
"""

import logging

_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def configure_logging(level: int = logging.INFO) -> None:
    """Idempotent: safe to call more than once in the same process (e.g. a
    script re-invoked, or imported by something that also configures
    logging) without stacking duplicate handlers."""
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(handler)
    root.setLevel(level)
