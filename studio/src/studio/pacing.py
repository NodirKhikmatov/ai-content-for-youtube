"""Shared narration-pacing math.

Storytelling (hook must speak in under 8 seconds) and Script Writer (whole
script must land in the 8-15 minute target from blueprint.md Section 2)
both need the same word-count-to-seconds conversion. Keeping it in one
place means they can't silently drift onto different assumptions about how
fast narration is spoken.
"""

WORDS_PER_MINUTE = 150  # standard documentary narration pace


def seconds_for_words(count: int) -> float:
    return count / WORDS_PER_MINUTE * 60


def words_for_seconds(seconds: float) -> int:
    return round(seconds / 60 * WORDS_PER_MINUTE)


def word_count(text: str) -> int:
    return len(text.split())
