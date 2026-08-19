"""Records that a video was actually published, after a human has manually
uploaded it through YouTube Studio — see agents/publishing.py's module
docstring for why that agent never sets status="published" itself. Shared
by scripts/mark_published.py's CLI and web/app.py's dashboard.
"""

from datetime import UTC, datetime

from studio import db


def mark_published(video_id: str, youtube_ref: str) -> str:
    youtube_video_id = youtube_ref.rsplit("/", 1)[-1].split("=")[-1]
    db.update_video(
        video_id,
        status="published",
        youtube_video_id=youtube_video_id,
        published_at=datetime.now(UTC),
    )
    return youtube_video_id
