"""Central settings, loaded from the environment / .env.

See ../../.env.example for the full list and where each key comes from.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    openai_api_key: str | None = None

    elevenlabs_api_key: str | None = None
    # "elevenlabs" (default, real, paid — and even ElevenLabs' free plan
    # rejects library-voice calls via the API) or "fake" (macOS `say` +
    # ffmpeg, free, no network call) — see tools/voice.py's FakeTTSBackend.
    voice_backend: str = "elevenlabs"
    # Kling's real API (docs.qingque.cn) authenticates with a signed JWT
    # generated from an access-key/secret-key pair, not a single static
    # bearer token — see tools/video_gen.py's module docstring.
    kling_access_key: str | None = None
    kling_secret_key: str | None = None
    # "kling" (real, paid, needs the two keys above), "higgsfield" (real,
    # paid/credits, needs the two keys below), or "fake" (local ffmpeg
    # synthetic clips, free, no network call) — see tools/video_gen.py.
    video_gen_backend: str = "kling"
    # Higgsfield issues a key_id/key_secret pair (cloud.higgsfield.ai
    # dashboard), not a single API key — see tools/video_gen.py's
    # HiggsfieldBackend.
    higgsfield_key_id: str | None = None
    higgsfield_key_secret: str | None = None
    # Model slug passed to Higgsfield's text2video endpoint — swap this to
    # try a different model on the platform without a code change (that
    # cross-model flexibility under one account is Higgsfield's whole
    # pitch vs. a single-vendor backend like Kling).
    higgsfield_model: str = "seedance-2.0"
    deepgram_api_key: str | None = None
    # "deepgram" (real, paid) or "fake" (fabricates word timestamps from the
    # known script instead of transcribing, free, no network call) — see
    # tools/transcribe.py's fake_transcribe.
    transcribe_backend: str = "deepgram"
    # "gemini" (real, paid) or "fake" (fixed high rubric scores, free, no
    # network call, no video upload) — see agents/quality_review.py's
    # _fake_verdict.
    quality_review_backend: str = "gemini"

    tavily_api_key: str | None = None
    voyage_api_key: str | None = None

    youtube_client_id: str | None = None
    youtube_client_secret: str | None = None
    youtube_refresh_token: str | None = None

    # Optional: lets Quality Review's human-in-the-loop decision happen
    # from a phone instead of requiring you at the terminal. Both must be
    # set for tools/telegram.py to activate; if either is missing,
    # run_pipeline.py falls back to the terminal prompt exactly as before.
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    database_url: str = "postgresql://studio:studio@localhost:5434/studio"

    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str = "turning-point-media"

    # Plain Homebrew `ffmpeg` has no libass support, so the `subtitles`
    # filter (caption burn-in) doesn't exist in it at all — needs
    # `brew install ffmpeg-full` (keg-only) and these pointed at it, e.g.
    # /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg. See README.md.
    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"


from pathlib import Path
from typing import Any


settings = Settings()


def update_settings(**kwargs: Any) -> None:
    """Updates settings in memory and writes them to .env file."""
    env_path = Path(".env")
    env_dict: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_dict[k.strip()] = v.strip()

    for k, v in kwargs.items():
        if v is not None:
            val_str = str(v).strip()
            env_key = k.upper()
            env_dict[env_key] = val_str
            if hasattr(settings, k):
                setattr(settings, k, val_str or None if "key" in k or "token" in k or "id" in k or "secret" in k else val_str)

    lines = [f"{k}={v}" for k, v in env_dict.items()]
    env_path.write_text("\n".join(lines) + "\n")
