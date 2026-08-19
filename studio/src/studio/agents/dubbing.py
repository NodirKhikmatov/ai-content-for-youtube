"""Multi-Language Dubbing Agent.

Translates produced video scripts into target languages (Uzbek, Russian, English,
Spanish, German, Turkish, French, Japanese, Korean, etc.), synthesizes native voiceovers,
re-times visual clips, mixes ducked BGM soundtrack, and burns in synchronized subtitles.
"""

import logging
from pathlib import Path
from typing import Any

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from studio import db
from studio.agents.subtitle import words_to_srt
from studio.config import settings
from studio.tools.audio_fx import mix_master_soundtrack
from studio.tools.ffmpeg_utils import (
    burn_subtitles,
    concat_clips,
    extract_audio,
    match_video_to_audio_duration,
    mux_audio_over_video,
    probe_duration_seconds,
)
from studio.tools.llm import invoke_with_retry
from studio.tools.transcribe import fake_transcribe, transcribe
from studio.tools.video_gen import FakeVideoBackend, HiggsfieldBackend, KlingBackend
from studio.tools.voice import ElevenLabsBackend, FakeTTSBackend, voice_for_video

log = logging.getLogger(__name__)

MEDIA_DIR = Path("media")
MODEL = "claude-sonnet-5"

SUPPORTED_LANGUAGES = {
    "uz": "O'zbekcha 🇺🇿",
    "ru": "Русский 🇷🇺",
    "en": "English 🇬🇧",
    "es": "Español 🇪🇸",
    "de": "Deutsch 🇩🇪",
    "fr": "Français 🇫🇷",
    "tr": "Türkçe 🇹🇷",
    "ja": "日本語 🇯🇵",
    "ko": "한국어 🇰🇷",
}


class TranslatedScript(BaseModel):
    translated_title: str = Field(description="Translated high-CTR title in target language")
    translated_narration: str = Field(description="Full translated voiceover script in target language")


def _translation_prompt(script: str, title: str, target_lang: str, lang_name: str) -> str:
    return (
        f"You are a master YouTube video translator and dubbing director.\n\n"
        f"Translate the following video script and title from English to {lang_name} ({target_lang}).\n"
        f"Requirements:\n"
        f"1. Natural, engaging, dramatic spoken prose for YouTube narration.\n"
        f"2. Match the cadence and emotional intensity of the original.\n"
        f"3. Keep the translation concise so spoken runtime closely matches the original.\n\n"
        f"Original Title: {title}\n"
        f"Original Script:\n{script}"
    )


def translate_script(script: str, title: str, target_lang: str) -> tuple[str, str]:
    """Translates script and title into the target language."""
    lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

    if not settings.anthropic_api_key:
        # Deterministic offline template for demonstration
        if target_lang == "uz":
            return (
                f"{title} (O'zbek tilida)",
                f"Ushbu hikoya hamma narsani o'zgartirib yuborgan burilish nuqtasi haqida. "
                f"Hech kim voqealar bunday rivojlanishini kutmagan edi. "
                f"Tafsilotlar va barcha haqiqatni ushbu maxsus sonda ko'rishingiz mumkin.",
            )
        elif target_lang == "ru":
            return (
                f"{title} (На русском)",
                f"Эта история о поворотном моменте, который изменил всё. "
                f"Никто не ожидал такого поворота событий. "
                f"Все подробности и скрытые факты в этом выпуске.",
            )
        return (
            f"{title} ({lang_name})",
            f"This is the translated edition of {title} in {lang_name}. "
            f"Discover the turning point that flipped everything.",
        )

    try:
        llm = ChatAnthropic(model=MODEL, api_key=settings.anthropic_api_key)  # type: ignore[call-arg,arg-type]
        structured_llm = llm.with_structured_output(TranslatedScript)
        res: TranslatedScript = invoke_with_retry(
            structured_llm, _translation_prompt(script, title, target_lang, lang_name)
        )
        return res.translated_title, res.translated_narration
    except Exception as exc:
        log.warning("Translation LLM failed (%s) — using fallback template", exc)
        return (f"{title} ({lang_name})", f"{script}")


def dub_video(video_id: str, target_lang: str) -> dict[str, Any]:
    """Dubs an existing produced video into target language."""
    video = db.get_video(video_id)
    if not video:
        raise ValueError(f"Video {video_id} not found")

    case = db.get_case(video["case_id"]) if video.get("case_id") else {"title": video.get("title", "Video"), "jurisdiction": "General"}
    script = video.get("script") or ""
    if not script:
        # Fallback to beat sheet or brief
        brief = db.get_latest_agent_output(video_id, "deep_research") or {}
        script = brief.get("thesis", f"Story of {case['title']}")

    lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
    log.info("dubbing: starting translation into %s for video %s", lang_name, video_id)

    dub_dir = MEDIA_DIR / str(video_id) / "dubbed" / target_lang
    dub_dir.mkdir(parents=True, exist_ok=True)

    # 1. Translate
    trans_title, trans_narration = translate_script(script, case.get("title", "Video"), target_lang)

    # 2. Synthesize voice in target language
    voice_backend = FakeTTSBackend() if settings.voice_backend == "fake" else ElevenLabsBackend()
    voice_id = voice_for_video(video_id)
    voice_audio_path = dub_dir / "voice.mp3"
    voice_audio_path.write_bytes(voice_backend.synthesize(trans_narration, voice_id))
    narration_seconds = probe_duration_seconds(voice_audio_path)

    # 3. Obtain visual clips
    # Look for original clips in video_clip_paths or assembled video
    original_assembled = Path(video.get("assembled_video_path") or (MEDIA_DIR / str(video_id) / "assembled.mp4"))
    matched_video_path = dub_dir / "matched.mp4"
    master_audio_path = dub_dir / "master_audio.aac"
    assembled_dub_path = dub_dir / "assembled.mp4"

    if original_assembled.exists():
        match_video_to_audio_duration(original_assembled, narration_seconds, matched_video_path)
    else:
        # Generate synthetic fallback clip if original media missing
        fake_backend = FakeVideoBackend()
        clip_path = dub_dir / "clip.mp4"
        clip_path.write_bytes(fake_backend.generate_clip(trans_narration, int(narration_seconds) + 1, aspect_ratio="16:9"))
        match_video_to_audio_duration(clip_path, narration_seconds, matched_video_path)
        clip_path.unlink(missing_ok=True)

    # 4. Mix with ducked BGM
    jurisdiction = (case.get("jurisdiction") or "").lower()
    is_webtoon = any(k in jurisdiction for k in ("webtoon", "manhwa", "manga", "anime"))
    mix_master_soundtrack(
        voice_path=voice_audio_path,
        out_path=master_audio_path,
        is_webtoon=is_webtoon,
        bgm_volume=settings.bgm_volume,
        enable_bgm=settings.bgm_enabled,
    )

    # 5. Mux audio over video
    mux_audio_over_video(matched_video_path, master_audio_path, assembled_dub_path)
    matched_video_path.unlink(missing_ok=True)
    master_audio_path.unlink(missing_ok=True)

    # 6. Transcribe & Burn Subtitles
    extracted_audio_path = dub_dir / "for_transcription.mp3"
    extract_audio(assembled_dub_path, extracted_audio_path)
    try:
        if settings.transcribe_backend == "fake":
            result = fake_transcribe(extracted_audio_path, trans_narration)
        else:
            result = transcribe(extracted_audio_path.read_bytes())
    finally:
        extracted_audio_path.unlink(missing_ok=True)

    srt_path = dub_dir / "captions.srt"
    srt_path.write_text(words_to_srt(result["words"]))

    final_cut_path = dub_dir / "final_dubbed.mp4"
    try:
        burn_subtitles(assembled_dub_path, srt_path, final_cut_path)
    except Exception as exc:
        log.warning("dubbing: subtitle burn-in failed (%s) — using assembled cut", exc)
        final_cut_path = assembled_dub_path

    output = {
        "target_lang": target_lang,
        "lang_name": lang_name,
        "translated_title": trans_title,
        "translated_narration": trans_narration,
        "final_path": str(final_cut_path),
        "duration_seconds": narration_seconds,
    }

    db.record_agent_run(
        video_id,
        f"dubbing_{target_lang}",
        "succeeded",
        input={"target_lang": target_lang, "lang_name": lang_name},
        output=output,
    )

    log.info("dubbing: completed %s cut at %s (%.1fs)", lang_name, final_cut_path, narration_seconds)
    return output
