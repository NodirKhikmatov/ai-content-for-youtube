"""Retry wrapper for direct httpx calls (Tavily, Deepgram, Kling) — none of
these go through a vendor SDK, unlike Anthropic's client, which retries
transient failures on its own by default. This closes the same gap those
SDKs already close for themselves.

Retries only what's actually worth retrying: connection failures, timeouts,
HTTP 429, and HTTP 5xx. Never retries a plain 4xx — an invalid API key or a
malformed request fails identically on attempt two, so retrying it just
delays the real error behind a few seconds of backoff.
"""

import logging
import time
from collections.abc import Callable
from typing import TypeVar

import httpx

log = logging.getLogger(__name__)

T = TypeVar("T")

MAX_ATTEMPTS = 3
BASE_DELAY_SECONDS = 1.0

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    return isinstance(exc, _RETRYABLE_EXCEPTIONS)


def with_retry(call: Callable[[], T]) -> T:
    attempt = 0
    while True:
        attempt += 1
        try:
            return call()
        except Exception as exc:
            if not _is_retryable(exc) or attempt >= MAX_ATTEMPTS:
                raise
            delay = BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            log.warning(
                "Retryable error on attempt %d/%d (%s) — retrying in %.1fs",
                attempt,
                MAX_ATTEMPTS,
                exc,
                delay,
            )
            time.sleep(delay)
