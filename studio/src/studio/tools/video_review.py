"""Gemini video-understanding client for Quality Review's LLM-as-judge pass
(blueprint.md Section 4.5: "Gemini 3.1 Pro (native video understanding)").

A video needs uploading and server-side processing before it can be
referenced in a prompt, unlike a small inline image — a genuinely different
API shape from the structured-output plumbing the Claude-based agents use,
so this doesn't try to force it through the same pattern. API surface
confirmed against the installed google-genai SDK (files.upload / files.get
/ models.generate_content), not guessed — but the model name itself
("gemini-3-pro") is this project's Jan-2026-training-cutoff best guess for
what "Gemini 3.1 Pro" resolves to as an API model string; verify against
https://ai.google.dev/gemini-api/docs/models before trusting this live.
"""

import time
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from studio.config import settings

MODEL = "gemini-3-pro"
POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 120

T = TypeVar("T", bound=BaseModel)


def review_video(video_path: str, prompt: str, response_schema: type[T]) -> T:
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY missing — Quality Review needs it. Get a key at "
            "aistudio.google.com and add it to .env."
        )
    client = genai.Client(api_key=settings.gemini_api_key)
    uploaded = client.files.upload(file=video_path)
    assert uploaded.name is not None, "an uploaded file always has a name"

    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while uploaded.state and uploaded.state.name == "PROCESSING" and time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS)
        uploaded = client.files.get(name=uploaded.name)

    if uploaded.state and uploaded.state.name == "FAILED":
        raise RuntimeError(f"Gemini file processing failed for {video_path}")

    response = client.models.generate_content(
        model=MODEL,
        contents=[uploaded, prompt],  # type: ignore[arg-type]
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        ),
    )
    result = response.parsed
    if not isinstance(result, response_schema):
        raise RuntimeError(f"Gemini response did not parse as {response_schema.__name__}")
    return result
