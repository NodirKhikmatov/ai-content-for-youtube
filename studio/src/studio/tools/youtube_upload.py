"""YouTube Data API v3 direct upload and scheduling tool.

Uploads long-form videos and vertical shorts directly to a connected YouTube channel
using Google OAuth2 credentials, sets video metadata (title, description, tags),
and uploads high-CTR AI thumbnails.
"""

import hashlib
import logging
from pathlib import Path
from typing import Any

from studio.config import settings

log = logging.getLogger(__name__)


def upload_video_to_youtube(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    privacy_status: str = "unlisted",
    category_id: str = "24",  # 24: Entertainment, 27: Education
    thumbnail_path: Path | None = None,
) -> dict[str, Any]:
    """Uploads a video to YouTube Data API v3 and optionally attaches a thumbnail."""
    if not video_path.exists():
        raise FileNotFoundError(f"Video file {video_path} not found")

    # If YouTube OAuth is configured in .env / settings:
    if settings.youtube_refresh_token and settings.youtube_client_id and settings.youtube_client_secret:
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds = Credentials(
                token=None,
                refresh_token=settings.youtube_refresh_token,
                client_id=settings.youtube_client_id,
                client_secret=settings.youtube_client_secret,
                token_uri="https://oauth2.googleapis.com/token",
            )
            youtube = build("youtube", "v3", credentials=creds)

            body = {
                "snippet": {
                    "title": title[:100],
                    "description": description[:5000],
                    "tags": tags[:30],
                    "categoryId": category_id,
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False,
                },
            }

            media_body = MediaFileUpload(
                str(video_path),
                chunksize=-1,
                resumable=True,
                mimetype="video/mp4",
            )

            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media_body,
            )
            response = request.execute()
            yt_id = response.get("id")

            # Upload thumbnail if available
            if yt_id and thumbnail_path and thumbnail_path.exists():
                try:
                    thumb_media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
                    youtube.thumbnails().set(videoId=yt_id, media_body=thumb_media).execute()
                    log.info("youtube_upload: attached thumbnail %s to video %s", thumbnail_path, yt_id)
                except Exception as thumb_exc:
                    log.warning("youtube_upload: thumbnail upload failed (%s)", thumb_exc)

            log.info("youtube_upload: successfully published live video %s (https://youtu.be/%s)", yt_id, yt_id)
            return {
                "youtube_video_id": yt_id,
                "url": f"https://youtu.be/{yt_id}",
                "status": "live",
                "privacy": privacy_status,
            }
        except Exception as exc:
            log.error("youtube_upload: live upload failed (%s) — falling back to dev simulation", exc)
            raise

    # Safe zero-cost dev simulation mode
    sim_hash = hashlib.md5(f"{title}_{video_path}".encode()).hexdigest()[:11]
    sim_id = f"sim_{sim_hash}"
    log.info(
        "youtube_upload [simulation]: simulated publish for '%s' -> %s (privacy=%s)",
        title,
        sim_id,
        privacy_status,
    )
    return {
        "youtube_video_id": sim_id,
        "url": f"https://youtu.be/{sim_id}",
        "status": "simulated",
        "privacy": privacy_status,
        "note": "Simulated upload. To enable live uploads, add YouTube OAuth credentials in /settings.",
    }
