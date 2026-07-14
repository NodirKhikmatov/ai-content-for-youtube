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
    # Kling's real API (docs.qingque.cn) authenticates with a signed JWT
    # generated from an access-key/secret-key pair, not a single static
    # bearer token — see tools/video_gen.py's module docstring.
    kling_access_key: str | None = None
    kling_secret_key: str | None = None
    deepgram_api_key: str | None = None

    tavily_api_key: str | None = None
    voyage_api_key: str | None = None

    youtube_client_id: str | None = None
    youtube_client_secret: str | None = None
    youtube_refresh_token: str | None = None

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


settings = Settings()
