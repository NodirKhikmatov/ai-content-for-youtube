"""Thumbnail Generator Tool.

Renders 3 distinct high-impact 16:9 YouTube thumbnails (1280x720) for a given video
using Pillow (and optional AI image backends).
"""

import hashlib
import logging
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720
MEDIA_DIR = Path("media")


def _get_font(size: int) -> ImageFont.ImageFont:
    try:
        # Standard system fonts on macOS / Linux
        for font_name in ["Arial Bold.ttf", "Arial.ttf", "Helvetica.ttc", "DejaVuSans-Bold.ttf"]:
            try:
                return ImageFont.truetype(font_name, size)
            except OSError:
                continue
    except Exception:
        pass
    return ImageFont.load_default()


def generate_synthetic_thumbnail(
    title: str,
    subtitle: str,
    badge_text: str,
    variation_idx: int,
    output_path: Path,
) -> Path:
    """Generates a high-contrast, clickable YouTube thumbnail (1280x720)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 3 distinct color palettes
    palettes = [
        # Palette 1: Dark Slate + Neon Electric Indigo / Violet (Webtoon/Tech)
        {"bg1": (15, 10, 35), "bg2": (45, 20, 85), "accent": (140, 90, 255), "glow": (255, 60, 180), "badge_bg": (230, 40, 100)},
        # Palette 2: Obsidian + Crimson Flame / Gold (Dramatic Action/Crime)
        {"bg1": (20, 5, 10), "bg2": (70, 15, 25), "accent": (255, 60, 60), "glow": (255, 190, 40), "badge_bg": (220, 30, 30)},
        # Palette 3: Deep Teal / Emerald + Radiant Cyan (Mystery/Level-up)
        {"bg1": (5, 20, 25), "bg2": (10, 55, 65), "accent": (0, 230, 200), "glow": (60, 180, 255), "badge_bg": (0, 160, 230)},
    ]
    p = palettes[variation_idx % len(palettes)]

    img = Image.new("RGB", (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), color=p["bg1"])
    draw = ImageDraw.Draw(img)

    # 1. Gradient Background
    for y in range(THUMBNAIL_HEIGHT):
        ratio = y / THUMBNAIL_HEIGHT
        r = int(p["bg1"][0] * (1 - ratio) + p["bg2"][0] * ratio)
        g = int(p["bg1"][1] * (1 - ratio) + p["bg2"][1] * ratio)
        b = int(p["bg1"][2] * (1 - ratio) + p["bg2"][2] * ratio)
        draw.line([(0, y), (THUMBNAIL_WIDTH, y)], fill=(r, g, b))

    # 2. Glowing Diagonal Slash / Energy Rays
    seed_val = int(hashlib.md5(title.encode()).hexdigest(), 16) % 100
    for i in range(5):
        offset = i * 40 + seed_val
        draw.line(
            [(0, THUMBNAIL_HEIGHT - offset), (THUMBNAIL_WIDTH, offset)],
            fill=(*p["glow"], 40),
            width=8,
        )

    # 3. Outer Neon Border
    draw.rectangle(
        [(15, 15), (THUMBNAIL_WIDTH - 15, THUMBNAIL_HEIGHT - 15)],
        outline=p["accent"],
        width=6,
    )

    # 4. Top Category Badge
    badge_font = _get_font(28)
    badge_str = f" 🔥 {badge_text.upper()} "
    badge_w = len(badge_str) * 16 + 20
    draw.rounded_rectangle(
        [(60, 50), (60 + badge_w, 105)],
        radius=12,
        fill=p["badge_bg"],
    )
    draw.text((72, 62), badge_str, fill=(255, 255, 255), font=badge_font)

    # 5. Massive Punchy Title Text (2-3 words per line)
    title_font = _get_font(58)
    words = title.split()
    lines = []
    curr = []
    for w in words[:10]:
        curr.append(w)
        if len(curr) >= 3 or len(" ".join(curr)) > 20:
            lines.append(" ".join(curr).upper())
            curr = []
    if curr:
        lines.append(" ".join(curr).upper())

    y_pos = 150
    for line in lines[:3]:
        # Drop shadow for extreme readability
        draw.text((63, y_pos + 4), line, fill=(0, 0, 0), font=title_font)
        draw.text((58, y_pos + 4), line, fill=(0, 0, 0), font=title_font)
        draw.text((60, y_pos), line, fill=(255, 255, 255), font=title_font)
        y_pos += 75

    # 6. Subtitle / Hook Bar
    if subtitle:
        sub_font = _get_font(32)
        sub_text = subtitle[:65]
        draw.rounded_rectangle(
            [(60, y_pos + 20), (THUMBNAIL_WIDTH - 60, y_pos + 80)],
            radius=10,
            fill=(0, 0, 0),
            outline=p["accent"],
            width=2,
        )
        draw.text((80, y_pos + 32), f"⚡ {sub_text}", fill=p["glow"], font=sub_font)

    img.save(output_path, "JPEG", quality=95)
    log.info("Saved thumbnail variation %d to %s", variation_idx, output_path)
    return output_path


def generate_video_thumbnails(
    video_id: str,
    title: str,
    niche: str,
    turning_point: str,
    prompts: list[str],
) -> list[str]:
    """Generates 3 thumbnails for a video and returns local file paths."""
    thumb_dir = MEDIA_DIR / video_id / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    paths: list[str] = []
    badge_labels = [
        niche.split("-")[-1].strip() if "-" in niche else "MUST WATCH",
        "AWAKENED" if "webtoon" in niche.lower() else "THE TURNING POINT",
        "VIRAL RECAP" if "webtoon" in niche.lower() else "FULL STORY",
    ]

    for i in range(3):
        out_path = thumb_dir / f"thumbnail_{i + 1}.jpg"
        sub_text = prompts[i] if i < len(prompts) else turning_point
        generate_synthetic_thumbnail(
            title=title,
            subtitle=sub_text[:60],
            badge_text=badge_labels[i],
            variation_idx=i,
            output_path=out_path,
        )
        paths.append(str(out_path))

    return paths
