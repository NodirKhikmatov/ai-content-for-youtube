"""Records that a video was actually published, after a human has manually
uploaded it through YouTube Studio (blueprint.md Section 8, Day 7 — the
Data API write path isn't automated until Phase 2).

agents/publishing.py never sets status="published" itself, on purpose:
that would claim an upload happened when it hasn't. This script is the
real confirmation step, run by hand once it has — same logic as
web/app.py's "Mark Published" form, shared via studio.publish.

Usage:
    python scripts/mark_published.py <video_id> <youtube_url_or_id>
"""

import sys

from studio.publish import mark_published


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(1)
    youtube_video_id = mark_published(sys.argv[1], sys.argv[2])
    print(f"Marked {sys.argv[1]} as published (youtube_video_id={youtube_video_id})")


if __name__ == "__main__":
    main()
