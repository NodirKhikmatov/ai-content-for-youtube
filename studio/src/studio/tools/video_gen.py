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

HiggsfieldBackend, added later: an aggregator that fronts multiple video
models (Kling, Sora, Veo, Seedance, ...) behind one account, added as a
second real backend rather than a Kling replacement — same reasoning as
this module's own Kling/Veo split above, just one layer up. Its exact API
surface (base URL, endpoint path, job shape) is this project's best effort
from public docs and the official higgsfield-js/higgsfield-client SDKs,
*not* a verified-live integration (no API key was available to test
against while building this) — same caveat as Kling above. Verify against
your Higgsfield Cloud dashboard's current docs before trusting this live.
Auth is key_id:key_secret (issued at cloud.higgsfield.ai), not a single
key — confirmed against the official SDKs' credential format, unlike the
endpoint/response shape.
"""

import logging
import subprocess
import tempfile
import time
from pathlib import Path
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
    def generate_clip(
        self, prompt: str, duration_seconds: int, aspect_ratio: str = "16:9"
    ) -> bytes: ...


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

    def generate_clip(
        self, prompt: str, duration_seconds: int = 5, aspect_ratio: str = "16:9"
    ) -> bytes:
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
            json={
                "prompt": prompt,
                "duration": duration_seconds,
                "mode": "std",
                "aspect_ratio": aspect_ratio,
            },
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


HIGGSFIELD_BASE_URL = "https://platform.higgsfield.ai"
HIGGSFIELD_POLL_INTERVAL_SECONDS = 2  # matches the official SDK's default pollInterval
HIGGSFIELD_POLL_TIMEOUT_SECONDS = 300  # matches the official SDK's default maxPollTime


class HiggsfieldBackend:
    def __init__(self) -> None:
        if not settings.higgsfield_key_id or not settings.higgsfield_key_secret:
            raise RuntimeError(
                "HIGGSFIELD_KEY_ID/HIGGSFIELD_KEY_SECRET missing — Video Generation "
                "needs both (a key_id/key_secret pair, not a single API key). Get "
                "them from your dashboard at cloud.higgsfield.ai and add them to .env."
            )
        self._client = httpx.Client(
            base_url=HIGGSFIELD_BASE_URL,
            timeout=30.0,
            headers={
                "Authorization": f"{settings.higgsfield_key_id}:{settings.higgsfield_key_secret}"
            },
        )

    def generate_clip(
        self, prompt: str, duration_seconds: int = 5, aspect_ratio: str = "16:9"
    ) -> bytes:
        # Not wrapped in with_retry, same reasoning as KlingBackend above:
        # this submits a new, billed generation job, which isn't safe to
        # blindly retry on a lost response.
        response = self._client.post(
            f"/v1/text2video/{settings.higgsfield_model}",
            json={
                "input": {
                    "prompt": prompt,
                    "duration": duration_seconds,
                    "aspect_ratio": aspect_ratio,
                }
            },
        )
        response.raise_for_status()
        job_id = response.json()["jobs"][0]["id"]

        deadline = time.monotonic() + HIGGSFIELD_POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            def _poll() -> httpx.Response:
                response = self._client.get(f"/v1/jobs/{job_id}")
                response.raise_for_status()
                return response

            job = with_retry(_poll).json()
            status = job.get("status")
            if status == "completed":
                video_url = job["results"]["raw"]["url"]

                def _download() -> httpx.Response:
                    response = httpx.get(video_url, timeout=60.0)
                    response.raise_for_status()
                    return response

                return with_retry(_download).content
            if status == "failed":
                raise RuntimeError(f"Higgsfield generation failed: {job.get('error')}")
            time.sleep(HIGGSFIELD_POLL_INTERVAL_SECONDS)

        raise TimeoutError(f"Higgsfield generation for job {job_id} did not finish in time")


class FakeVideoBackend:
    """Local, zero-cost stand-in for KlingBackend: same VideoGenBackend
    interface, but renders a synthetic ffmpeg test-pattern clip instead of
    calling Kling — no API key, no network call, no bill. For running the
    pipeline end to end and getting a real playable MP4 out the other end
    while Kling isn't configured. Not a visual substitute for Kling's actual
    output — see VIDEO_GEN_BACKEND in .env.example.

    The tone frequency is derived from the prompt so consecutive beats
    produce audibly/visibly distinct clips rather than six identical ones.
    aspect_ratio only switches between two fixed resolutions (16:9 and
    9:16, the two shapes this project actually needs — long-form and
    Shorts) rather than parsing arbitrary ratios.
    """

    def generate_clip(
        self, prompt: str, duration_seconds: int = 5, aspect_ratio: str = "16:9"
    ) -> bytes:
        frequency = 220 + (hash(prompt) % 440)
        size = "1080x1920" if aspect_ratio == "9:16" else "1280x720"
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "clip.mp4"
            result = subprocess.run(
                [
                    settings.ffmpeg_binary,
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"testsrc=duration={duration_seconds}:size={size}:rate=24",
                    "-f",
                    "lavfi",
                    "-i",
                    f"sine=frequency={frequency}:duration={duration_seconds}",
                    "-shortest",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-pix_fmt",
                    "yuv420p",
                    str(out_path),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed generating fake clip: {result.stderr[-2000:]}")
            return out_path.read_bytes()
