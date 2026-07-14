"""Video generation, vendor-agnostic interface. Kling only in Phase 1
(blueprint.md Section 8: "cheap bulk B-roll") — Veo for hero shots is a
later addition, deliberately behind this same VideoGenBackend interface
rather than hard-coded, because Sora 2 was fully deprecated about six
months after launch (blueprint.md Friction 05). Never assume one video-gen
vendor survives the build.

Kling's exact API surface (endpoint, auth scheme, job-polling shape) is
this project's best effort as of its Jan-2026 training cutoff, not a
verified-live integration — there's no official Python SDK to check
against the way there was for ElevenLabs. Verify against
https://docs.qingque.cn (Kling's API docs) or your account's current
integration guide before trusting this live.
"""

import logging
import time
from typing import Protocol

import httpx

from studio.config import settings

log = logging.getLogger(__name__)

KLING_BASE_URL = "https://api.klingai.com/v1"
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 300


class VideoGenBackend(Protocol):
    def generate_clip(self, prompt: str, duration_seconds: int) -> bytes: ...


class KlingBackend:
    def __init__(self) -> None:
        if not settings.kling_api_key:
            raise RuntimeError(
                "KLING_API_KEY missing — Video Generation needs it. Get a key "
                "at klingai.com and add it to .env."
            )
        self._client = httpx.Client(
            base_url=KLING_BASE_URL,
            headers={"Authorization": f"Bearer {settings.kling_api_key}"},
            timeout=30.0,
        )

    def generate_clip(self, prompt: str, duration_seconds: int = 5) -> bytes:
        submit = self._client.post(
            "/videos/text2video",
            json={"prompt": prompt, "duration": duration_seconds, "mode": "std"},
        )
        submit.raise_for_status()
        job_id = submit.json()["data"]["task_id"]

        deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            status = self._client.get(f"/videos/text2video/{job_id}")
            status.raise_for_status()
            body = status.json()["data"]
            if body["task_status"] == "succeed":
                video_url = body["task_result"]["videos"][0]["url"]
                video = httpx.get(video_url, timeout=60.0)
                video.raise_for_status()
                return video.content
            if body["task_status"] == "failed":
                raise RuntimeError(f"Kling generation failed: {body.get('task_status_msg')}")
            time.sleep(POLL_INTERVAL_SECONDS)

        raise TimeoutError(f"Kling generation for job {job_id} did not finish in time")
