"""tools/llm.py's invoke_with_retry — pure unit test, no network. Covers
the exact failure mode seen live twice in one afternoon (Deep Research's
gather pass, then its counterpoint pass): a structured-output call raising
ValidationError because Claude's response was missing a required field.
"""

import pytest
from pydantic import BaseModel, ValidationError

from studio.tools.llm import invoke_with_retry


class Thing(BaseModel):
    required_field: str


def test_succeeds_without_retry_when_valid():
    class FakeStructuredLLM:
        def invoke(self, _prompt):
            return Thing(required_field="ok")

    result = invoke_with_retry(FakeStructuredLLM(), "prompt")
    assert result.required_field == "ok"


def test_retries_once_on_validation_error_then_succeeds():
    calls = {"n": 0}

    class FakeStructuredLLM:
        def invoke(self, prompt):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ValidationError.from_exception_data("Thing", [])
            assert "missing required field" in prompt.lower()
            return Thing(required_field="ok")

    result = invoke_with_retry(FakeStructuredLLM(), "prompt")
    assert result.required_field == "ok"
    assert calls["n"] == 2


def test_second_failure_propagates():
    class FakeStructuredLLM:
        def invoke(self, _prompt):
            raise ValidationError.from_exception_data("Thing", [])

    with pytest.raises(ValidationError):
        invoke_with_retry(FakeStructuredLLM(), "prompt")
