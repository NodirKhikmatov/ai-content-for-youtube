"""Minimal Telegram Bot API client — direct httpx calls, no SDK, same
pattern this project already uses for Tavily/Deepgram (one small, stable
REST surface, not worth a dependency).

Used for exactly one thing: letting Quality Review's human-in-the-loop
decision happen from a phone instead of requiring you at the terminal
when a run pauses for review. Nothing else in the pipeline uses this —
it is not a general bot command interface, no /run or /status commands,
on purpose. scripts/run_pipeline.py falls back to the existing terminal
prompt whenever TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID aren't both set.
"""

import time
from pathlib import Path
from typing import Any

import httpx

from studio.config import settings
from studio.tools.retry import with_retry

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

# Telegram's own upload limit for a bot-sent file — send the real assembled
# video only if it fits; otherwise fall back to a text-only notification
# rather than trying to chunk or compress it (real scope creep for what
# this exists to do).
MAX_VIDEO_BYTES = 50 * 1024 * 1024

POLL_TIMEOUT_SECONDS = 30
DECISION_TIMEOUT_SECONDS = 3600  # give a human up to an hour to respond


def is_configured() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def _url(method: str) -> str:
    return TELEGRAM_API.format(token=settings.telegram_bot_token, method=method)


def send_message(text: str) -> None:
    def _call() -> httpx.Response:
        response = httpx.post(
            _url("sendMessage"),
            json={"chat_id": settings.telegram_chat_id, "text": text},
            timeout=30.0,
        )
        response.raise_for_status()
        return response

    with_retry(_call)


def send_video_if_small_enough(path: str, caption: str) -> bool:
    """Best-effort: returns False (no exception) if the file is too big or
    the upload fails, so the caller can fall back to a text-only message —
    same "degrade, don't block" posture as R2 upload elsewhere."""
    video_path = Path(path)
    if not video_path.exists() or video_path.stat().st_size > MAX_VIDEO_BYTES:
        return False
    try:
        with video_path.open("rb") as f:
            response = httpx.post(
                _url("sendVideo"),
                data={"chat_id": settings.telegram_chat_id, "caption": caption},
                files={"video": f},
                timeout=120.0,
            )
        response.raise_for_status()
        return True
    except Exception:
        return False


def _latest_update_id() -> int:
    response = httpx.get(_url("getUpdates"), params={"limit": 1, "offset": -1}, timeout=30.0)
    response.raise_for_status()
    results: list[dict[str, Any]] = response.json().get("result", [])
    return results[-1]["update_id"] if results else 0


def ask_for_decision(text: str) -> str:
    """Sends an Approve/Reject prompt with inline buttons and blocks
    (long-polling Telegram's own getUpdates, not a tight loop) until the
    button is tapped from the configured chat. Raises TimeoutError past
    DECISION_TIMEOUT_SECONDS rather than waiting forever."""
    offset = _latest_update_id() + 1

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Approve", "callback_data": "approve"},
                {"text": "Reject", "callback_data": "reject"},
            ]
        ]
    }

    def _prompt() -> httpx.Response:
        response = httpx.post(
            _url("sendMessage"),
            json={"chat_id": settings.telegram_chat_id, "text": text, "reply_markup": keyboard},
            timeout=30.0,
        )
        response.raise_for_status()
        return response

    with_retry(_prompt)

    deadline = time.monotonic() + DECISION_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = httpx.get(
            _url("getUpdates"),
            params={"offset": offset, "timeout": POLL_TIMEOUT_SECONDS},
            timeout=POLL_TIMEOUT_SECONDS + 10,
        )
        response.raise_for_status()
        for update in response.json().get("result", []):
            offset = update["update_id"] + 1
            callback = update.get("callback_query")
            if callback and callback.get("data") in ("approve", "reject"):
                httpx.post(
                    _url("answerCallbackQuery"),
                    json={"callback_query_id": callback["id"]},
                    timeout=30.0,
                )
                decision: str = callback["data"]
                return decision

    raise TimeoutError(
        f"No Telegram response within {DECISION_TIMEOUT_SECONDS}s — falling back to terminal."
    )
