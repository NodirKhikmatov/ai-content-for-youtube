"""tools/retry.py — pure unit tests, no network. Covers exactly the
Priority 7 requirement: retry transient failures and 429/5xx, never retry
a plain 4xx (invalid key, bad request, permission error)."""

import httpx
import pytest

from studio.tools.retry import with_retry


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


def test_succeeds_without_retry_on_first_try():
    calls = {"n": 0}

    def _call():
        calls["n"] += 1
        return "ok"

    assert with_retry(_call) == "ok"
    assert calls["n"] == 1


def test_retries_on_timeout_then_succeeds(monkeypatch):
    monkeypatch.setattr("studio.tools.retry.time.sleep", lambda _: None)
    calls = {"n": 0}

    def _call():
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ConnectTimeout("timed out")
        return "ok"

    assert with_retry(_call) == "ok"
    assert calls["n"] == 2


def test_retries_on_429_and_5xx(monkeypatch):
    monkeypatch.setattr("studio.tools.retry.time.sleep", lambda _: None)
    calls = {"n": 0}

    def _call():
        calls["n"] += 1
        if calls["n"] == 1:
            raise _status_error(429)
        if calls["n"] == 2:
            raise _status_error(503)
        return "ok"

    assert with_retry(_call) == "ok"
    assert calls["n"] == 3


def test_does_not_retry_on_401():
    calls = {"n": 0}

    def _call():
        calls["n"] += 1
        raise _status_error(401)

    with pytest.raises(httpx.HTTPStatusError):
        with_retry(_call)
    assert calls["n"] == 1


def test_does_not_retry_on_400():
    calls = {"n": 0}

    def _call():
        calls["n"] += 1
        raise _status_error(400)

    with pytest.raises(httpx.HTTPStatusError):
        with_retry(_call)
    assert calls["n"] == 1


def test_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr("studio.tools.retry.time.sleep", lambda _: None)
    calls = {"n": 0}

    def _call():
        calls["n"] += 1
        raise httpx.ConnectTimeout("always fails")

    with pytest.raises(httpx.ConnectTimeout):
        with_retry(_call)
    assert calls["n"] == 3  # MAX_ATTEMPTS
