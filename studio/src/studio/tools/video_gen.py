"""Video generation, vendor-agnostic interface. Kling only in Phase 1
(blueprint.md Section 8: "cheap bulk B-roll") — Veo for hero shots is a
later addition, deliberately behind this same VideoGenBackend interface
rather than hard-coded, because Sora 2 was fully deprecated about six
months after launch (blueprint.md Friction 05). Never assume one video-gen
vendor survives the build.

Kling's exact API surface (endpoint, job-polling shape) is this project's
best effort as of its Jan-2026 training cutoff, not a verified-live
integration — there's no official Python SDK to check against the way
there was for ElevenLabs. Verify against https://docs.qingque.cn (Kling's
API docs) or your account's current integration guide before trusting this
live.

Auth is *not* best-effort, though: Kling's official API authenticates with
a short-lived JWT signed (HS256) from an access-key/secret-key pair — not
a static bearer token — confirmed against docs.qingque.cn's auth section.
A prior version of this file treated KLING_API_KEY as a plain bearer token,
which would have failed authentication against every real request.
"""

import logging
import time
from typing import Protocol

import httpx
import jwt

from studio.config import settings
from studio.tools.retry import with_retry

log = logging.getLogger(__name__)

KLING_BASE_URL = "https://api.klingai.com/v1"
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 300

# JWT validity window: issued slightly in the past (clock-skew tolerance)
# and expiring well within Kling's documented max, regenerated fresh for
# every request rather than cached — simplest correct thing at MVP's
# request volume (a handful of clips per video, not a hot loop).
JWT_NOT_BEFORE_SKEW_SECONDS = 5
JWT_EXPIRY_SECONDS = 1800


class VideoGenBackend(Protocol):
    def generate_clip(self, prompt: str, duration_seconds: int) -> bytes: ...


def _kling_jwt(access_key: str, secret_key: str) -> str:
    now = int(time.time())
    payload = {
        "iss": access_key,
        "exp": now + JWT_EXPIRY_SECONDS,
        "nbf": now - JWT_NOT_BEFORE_SKEW_SECONDS,
    }
    return jwt.encode(payload, secret_key, algorithm="HS256", headers={"alg": "HS256", "typ": "JWT"})


class KlingBackend:
    def __init__(self) -> None:
        if not settings.kling_access_key or not settings.kling_secret_key:
            raise RuntimeError(
                "KLING_ACCESS_KEY/KLING_SECRET_KEY missing — Video Generation needs "
                "both (Kling issues an access-key/secret-key pair, not a single API "
                "key). Get them at klingai.com and add them to .env."
            )
        self._access_key = settings.kling_access_key
        self._secret_key = settings.kling_secret_key
        self._client = httpx.Client(base_url=KLING_BASE_URL, timeout=30.0)

    def _headers(self) -> dict[str, str]:
        token = _kling_jwt(self._access_key, self._secret_key)
        return {"Authorization": f"Bearer {token}"}

    def generate_clip(self, prompt: str, duration_seconds: int = 5) -> bytes:
        # Deliberately not wrapped in with_retry: this POST creates a new,
        # billed Kling generation job — it is not idempotent like the poll
        # and download calls below. If the request reaches Kling and the
        # job starts, but the *response* is lost (a timeout or connection
        # reset — exactly the failure mode with_retry exists to paper over
        # for safe calls), a blind retry here would submit a second,
        # duplicate, separately-billed job with no way to detect or clean
        # up the orphaned first one. A failed submit fails this clip
        # generation outright; retrying that decision belongs to the
        # caller (Video Generation agent raises and fails the whole run,
        # or a human re-runs the pipeline), not to a blanket transport
        # retry that can't tell "never reached the server" apart from
        # "reached it and maybe already succeeded".
        response = self._client.post(
            "/videos/text2video",
            json={"prompt": prompt, "duration": duration_seconds, "mode": "std"},
            headers=self._headers(),
        )
        response.raise_for_status()
        job_id = response.json()["data"]["task_id"]

        deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            # Re-derive headers each poll too: a slow-completing job can
            # legitimately outlive one JWT's expiry window.
            def _poll() -> httpx.Response:
                response = self._client.get(f"/videos/text2video/{job_id}", headers=self._headers())
                response.raise_for_status()
                return response

            body = with_retry(_poll).json()["data"]
            if body["task_status"] == "succeed":
                video_url = body["task_result"]["videos"][0]["url"]

                def _download() -> httpx.Response:
                    response = httpx.get(video_url, timeout=60.0)
                    response.raise_for_status()
                    return response

                return with_retry(_download).content
            if body["task_status"] == "failed":
                raise RuntimeError(f"Kling generation failed: {body.get('task_status_msg')}")
            time.sleep(POLL_INTERVAL_SECONDS)

        raise TimeoutError(f"Kling generation for job {job_id} did not finish in time")
