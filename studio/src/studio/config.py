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
    kling_api_key: str | None = None

    tavily_api_key: str | None = None

    youtube_client_id: str | None = None
    youtube_client_secret: str | None = None
    youtube_refresh_token: str | None = None

    database_url: str = "postgresql://studio:studio@localhost:5434/studio"

    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str = "turning-point-media"


settings = Settings()
