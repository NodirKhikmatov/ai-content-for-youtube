"""Shared retry wrapper for `with_structured_output(...).invoke(...)` calls.

Claude's tool-call output occasionally drops a required field even though
the schema declares it required — seen live, twice in one afternoon, on
two different Deep Research passes (`turning_point` missing from the
gather pass, then `thesis`/`turning_point` missing from the counterpoint
pass before that one got its own narrower schema). Not a prompt-wording
problem, since the same prompt succeeds most of the time — a transient
parse miss, not a systematic one. One retry with an explicit reminder of
what was missing, same pattern Storytelling/Script Writer already use for
their own domain-level retries (hook length, script pacing), just applied
generically here instead of duplicated per agent.

Every agent that calls `with_structured_output(...).invoke(...)` should
route through this rather than calling `.invoke()` directly.
"""

from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def invoke_with_retry(structured_llm, prompt: str) -> T:  # type: ignore[no-untyped-def,type-var]
    try:
        return structured_llm.invoke(prompt)
    except ValidationError as exc:
        missing = ", ".join(str(e["loc"][0]) for e in exc.errors() if e["type"] == "missing")
        retry_prompt = (
            f"{prompt}\n\nYour previous response was missing required field(s): "
            f"{missing or 'unknown'}. Return a complete response with every "
            f"required field filled in."
        )
        return structured_llm.invoke(retry_prompt)
