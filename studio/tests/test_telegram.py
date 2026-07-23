"""tools/telegram.py — mocks httpx so this runs without a real bot token.
Covers is_configured()'s fallback gate, send_video_if_small_enough()'s
size/failure handling, and ask_for_decision()'s poll-until-callback and
timeout behavior.
"""

import httpx
import pytest

from studio.tools import telegram


def _response(json_body: dict) -> httpx.Response:
    return httpx.Response(200, json=json_body, request=httpx.Request("GET", "https://x"))


def test_is_configured_requires_both_values(monkeypatch):
    monkeypatch.setattr(telegram.settings, "telegram_bot_token", None)
    monkeypatch.setattr(telegram.settings, "telegram_chat_id", "123")
    assert telegram.is_configured() is False

    monkeypatch.setattr(telegram.settings, "telegram_bot_token", "tok")
    monkeypatch.setattr(telegram.settings, "telegram_chat_id", "123")
    assert telegram.is_configured() is True


def test_send_video_returns_false_for_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.mp4"
    assert telegram.send_video_if_small_enough(str(missing), "caption") is False


def test_send_video_returns_false_when_too_large(tmp_path, monkeypatch):
    big = tmp_path / "big.mp4"
    big.write_bytes(b"x")
    monkeypatch.setattr(telegram, "MAX_VIDEO_BYTES", 0)  # anything is "too big"
    assert telegram.send_video_if_small_enough(str(big), "caption") is False


def test_send_video_returns_false_on_upload_failure(tmp_path, monkeypatch):
    small = tmp_path / "small.mp4"
    small.write_bytes(b"video bytes")

    def _boom(*_a, **_k):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(telegram.httpx, "post", _boom)
    assert telegram.send_video_if_small_enough(str(small), "caption") is False


def test_send_video_returns_true_on_success(tmp_path, monkeypatch):
    small = tmp_path / "small.mp4"
    small.write_bytes(b"video bytes")

    monkeypatch.setattr(telegram.httpx, "post", lambda *_a, **_k: _response({"ok": True}))
    assert telegram.send_video_if_small_enough(str(small), "caption") is True


def test_ask_for_decision_returns_on_matching_callback(monkeypatch):
    monkeypatch.setattr(telegram.settings, "telegram_bot_token", "tok")
    monkeypatch.setattr(telegram.settings, "telegram_chat_id", "123")

    calls = {"get": 0}

    def fake_get(url, **_k):
        calls["get"] += 1
        if "getUpdates" in url and calls["get"] == 1:
            return _response({"result": []})  # _latest_update_id: no history
        return _response(
            {
                "result": [
                    {"update_id": 5, "callback_query": {"id": "cb1", "data": "approve"}},
                ]
            }
        )

    monkeypatch.setattr(telegram.httpx, "get", fake_get)
    monkeypatch.setattr(telegram.httpx, "post", lambda *_a, **_k: _response({"ok": True}))

    assert telegram.ask_for_decision("Approve?") == "approve"


def test_ask_for_decision_times_out(monkeypatch):
    monkeypatch.setattr(telegram.settings, "telegram_bot_token", "tok")
    monkeypatch.setattr(telegram.settings, "telegram_chat_id", "123")
    monkeypatch.setattr(telegram, "DECISION_TIMEOUT_SECONDS", 0)

    monkeypatch.setattr(telegram.httpx, "get", lambda *_a, **_k: _response({"result": []}))
    monkeypatch.setattr(telegram.httpx, "post", lambda *_a, **_k: _response({"ok": True}))

    with pytest.raises(TimeoutError):
        telegram.ask_for_decision("Approve?")
