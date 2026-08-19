"""Dialogue and Character Role Parser.

Parses scripts with speaker tags (e.g. [NARRATOR], [HERO], [VILLAIN], [SYSTEM_AI])
for multi-character voice acting.
"""

import re
from typing import TypedDict


class DialogueSegment(TypedDict):
    role: str  # "narrator", "hero", "villain", "system_ai"
    text: str


ROLE_PATTERNS = {
    "hero": re.compile(r"^\[(HERO|PROTAGONIST|HUNTER|MAIN|MC)\]\s*:?\s*", re.IGNORECASE),
    "villain": re.compile(r"^\[(VILLAIN|ANTAGONIST|BOSS|ENEMY|MONSTER)\]\s*:?\s*", re.IGNORECASE),
    "system_ai": re.compile(r"^\[(SYSTEM|SYSTEM_AI|AI|STATUS|NOTIFICATION)\]\s*:?\s*", re.IGNORECASE),
    "narrator": re.compile(r"^\[(NARRATOR|VOICEOVER|HOST|SPEAKER)\]\s*:?\s*", re.IGNORECASE),
}


def parse_dialogue_segments(script: str) -> list[DialogueSegment]:
    """Parses a multi-speaker script into role-tagged segments."""
    lines = script.strip().split("\n")
    segments: list[DialogueSegment] = []

    current_role = "narrator"
    current_buffer: list[str] = []

    has_explicit_roles = False

    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue

        detected_role = None
        text_without_tag = cleaned_line

        for role, pattern in ROLE_PATTERNS.items():
            match = pattern.match(cleaned_line)
            if match:
                detected_role = role
                text_without_tag = cleaned_line[match.end() :].strip()
                has_explicit_roles = True
                break

        if detected_role:
            if current_buffer:
                segments.append({"role": current_role, "text": " ".join(current_buffer)})
                current_buffer = []
            current_role = detected_role
            if text_without_tag:
                current_buffer.append(text_without_tag)
        else:
            current_buffer.append(cleaned_line)

    if current_buffer:
        segments.append({"role": current_role, "text": " ".join(current_buffer)})

    if not has_explicit_roles:
        return [{"role": "narrator", "text": script.strip()}]

    return segments
