"""Web dashboard for "The Turning Point" pipeline — a fuller alternative to
driving everything through scripts/run_pipeline.py + tailing logs. Start
new runs, watch progress, approve/reject at Quality Review's human gate,
browse produced videos and Shorts, and record a manual publish — all from
the browser. See web/runner.py's module docstring for how this reconciles
LangGraph's single-process interrupt/resume constraint with being a
long-running server instead of a one-shot CLI invocation.

Run:
    uvicorn studio.web.app:app --reload
"""

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from studio import db
from studio.agents.quality_review import MIN_DIMENSION_SCORE
from studio.config import settings
from studio.publish import mark_published
from studio.web import runner

app = FastAPI(title="The Turning Point — Studio")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
CHANNEL_NAME = "The Turning Point"
MEDIA_DIR = Path("media")


def _channel_id():
    return db.get_channel_id(CHANNEL_NAME)


def _media_rel(path_str: str | None, video_id: str) -> str | None:
    """Path relative to media/{video_id}/, for building /media/{id}/{path}
    URLs — the DB and agent_runs.output store paths like
    "media/{id}/shorts/short.mp4", not just a filename, so a bare
    Path(...).name would drop the "shorts/" subdirectory and 404."""
    if not path_str:
        return None
    try:
        return str(Path(path_str).relative_to(MEDIA_DIR / video_id))
    except ValueError:
        return Path(path_str).name


@app.get("/")
def dashboard(request: Request):
    channel_id = _channel_id()
    context: dict[str, Any] = {
        "backlog_count": db.count_backlog(channel_id),
        "videos": db.list_videos(limit=10),
        "active_runs": runner.active_runs(),
        "video_backend": settings.video_gen_backend,
        "voice_backend": settings.voice_backend,
        "transcribe_backend": settings.transcribe_backend,
        "quality_review_backend": settings.quality_review_backend,
    }
    return templates.TemplateResponse(request, "index.html", context)


@app.post("/runs/start")
def start_new_run():
    handle = runner.start_run()
    return RedirectResponse(f"/runs/{handle.thread_id}", status_code=303)


@app.post("/videos/{video_id}/resume")
def resume_video(video_id: str):
    handle = runner.start_run(resume_video_id=video_id)
    return RedirectResponse(f"/runs/{handle.thread_id}", status_code=303)


@app.get("/runs/{thread_id}")
def run_status(request: Request, thread_id: str):
    handle = runner.RUNS.get(thread_id)
    if handle is None:
        return templates.TemplateResponse(
            request, "run_status.html", {"handle": None, "thread_id": thread_id}
        )
    agent_runs = db.get_agent_runs(handle.video_id) if handle.video_id else []
    review_media_rel = None
    if handle.interrupt_payload and handle.video_id:
        review_media_rel = _media_rel(
            handle.interrupt_payload.get("assembled_video_path"), handle.video_id
        )
    context: dict[str, Any] = {
        "handle": handle,
        "thread_id": thread_id,
        "agent_runs": agent_runs,
        "min_dimension_score": MIN_DIMENSION_SCORE,
        "review_media_rel": review_media_rel,
    }
    return templates.TemplateResponse(request, "run_status.html", context)


@app.post("/runs/{thread_id}/decide")
def decide(thread_id: str, decision: str = Form(...), notes: str = Form("")):
    runner.submit_decision(thread_id, decision, notes)
    return RedirectResponse(f"/runs/{thread_id}", status_code=303)


from studio.config import settings, update_settings


@app.get("/create")
def create_page(request: Request):
    return templates.TemplateResponse(request, "create.html", {})


@app.post("/runs/custom")
def start_custom_run(
    title: str = Form(...),
    turning_point: str = Form(""),
    niche: str = Form("General Documentary"),
    era: str = Form("Modern"),
    protagonist: str = Form(""),
    format_type: str = Form("documentary"),
):
    if format_type == "webtoon" and protagonist.strip():
        era = f"{era} (Protagonist: {protagonist.strip()})"

    custom_topic = {
        "title": title.strip(),
        "turning_point": turning_point.strip(),
        "niche": niche.strip(),
        "era": era.strip(),
        "protagonist": protagonist.strip(),
        "format_type": format_type.strip(),
    }
    handle = runner.start_run(custom_topic=custom_topic)
    return RedirectResponse(f"/runs/{handle.thread_id}", status_code=303)


@app.post("/runs/case/{case_id}")
def start_case_run(case_id: str):
    handle = runner.start_run(case_id=case_id)
    return RedirectResponse(f"/runs/{handle.thread_id}", status_code=303)


@app.get("/settings")
def settings_page(request: Request, saved: bool = False):
    context = {
        "settings": settings,
        "saved": saved,
    }
    return templates.TemplateResponse(request, "settings.html", context)


@app.post("/settings")
def save_settings(
    anthropic_api_key: str = Form(""),
    gemini_api_key: str = Form(""),
    openai_api_key: str = Form(""),
    tavily_api_key: str = Form(""),
    voyage_api_key: str = Form(""),
    elevenlabs_api_key: str = Form(""),
    kling_access_key: str = Form(""),
    kling_secret_key: str = Form(""),
    higgsfield_key_id: str = Form(""),
    higgsfield_key_secret: str = Form(""),
    higgsfield_model: str = Form("seedance-2.0"),
    deepgram_api_key: str = Form(""),
    voice_backend: str = Form("fake"),
    video_gen_backend: str = Form("fake"),
    transcribe_backend: str = Form("fake"),
    quality_review_backend: str = Form("fake"),
    telegram_bot_token: str = Form(""),
    telegram_chat_id: str = Form(""),
):
    update_settings(
        anthropic_api_key=anthropic_api_key or None,
        gemini_api_key=gemini_api_key or None,
        openai_api_key=openai_api_key or None,
        tavily_api_key=tavily_api_key or None,
        voyage_api_key=voyage_api_key or None,
        elevenlabs_api_key=elevenlabs_api_key or None,
        kling_access_key=kling_access_key or None,
        kling_secret_key=kling_secret_key or None,
        higgsfield_key_id=higgsfield_key_id or None,
        higgsfield_key_secret=higgsfield_key_secret or None,
        higgsfield_model=higgsfield_model or "seedance-2.0",
        deepgram_api_key=deepgram_api_key or None,
        voice_backend=voice_backend,
        video_gen_backend=video_gen_backend,
        transcribe_backend=transcribe_backend,
        quality_review_backend=quality_review_backend,
        telegram_bot_token=telegram_bot_token or None,
        telegram_chat_id=telegram_chat_id or None,
    )
    return RedirectResponse("/settings?saved=true", status_code=303)


@app.get("/backlog")
def backlog(request: Request):
    channel_id = _channel_id()
    context = {"cases": db.list_backlog(channel_id, limit=100)}
    return templates.TemplateResponse(request, "backlog.html", context)


@app.get("/videos")
def videos(request: Request):
    context = {"videos": db.list_videos(limit=200)}
    return templates.TemplateResponse(request, "videos.html", context)


@app.get("/videos/{video_id}")
def video_detail(request: Request, video_id: str):
    video = db.get_video(video_id)
    agent_runs = db.get_agent_runs(video_id)
    beat_sheet = db.get_latest_agent_output(video_id, "storytelling")
    quality_verdict = db.get_latest_agent_output(video_id, "quality_review")
    compliance_verdict = db.get_latest_agent_output(video_id, "compliance")
    publishing_output = db.get_latest_agent_output(video_id, "publishing") or {}
    thumb_paths = publishing_output.get("thumbnail_paths", [])
    thumb_media_urls = [f"/media/{video_id}/thumbnails/thumbnail_{i + 1}.jpg" for i in range(len(thumb_paths))]

    context: dict[str, Any] = {
        "video": video,
        "video_id": video_id,
        "agent_runs": agent_runs,
        "can_make_short": beat_sheet is not None,
        "quality_verdict": quality_verdict,
        "compliance_verdict": compliance_verdict,
        "short_output": short_output,
        "short_handle": short_handle,
        "publishing_output": publishing_output,
        "thumb_media_urls": thumb_media_urls,
        "min_dimension_score": MIN_DIMENSION_SCORE,
        "assembled_media_rel": _media_rel(video.get("assembled_video_path"), video_id),
        "short_media_rel": _media_rel(
            short_output.get("final_path") if short_output else None, video_id
        ),
    }
    return templates.TemplateResponse(request, "video_detail.html", context)


from studio.agents.seo import generate_seo_metadata
from studio.tools.thumbnail import generate_video_thumbnails


@app.post("/videos/{video_id}/seo")
def generate_seo(video_id: str):
    video = db.get_video(video_id)
    case = db.get_case(video["case_id"]) if video.get("case_id") else {"title": video.get("title", "Video"), "jurisdiction": "General", "turning_point": ""}
    brief = db.get_latest_agent_output(video_id, "deep_research") or {}
    script = video.get("script") or ""

    seo = generate_seo_metadata(case, brief, script)
    main_title = seo.viral_titles[0] if seo.viral_titles else case["title"]

    niche = case.get("jurisdiction", "General")
    tp = case.get("turning_point", "")
    thumbnail_paths = generate_video_thumbnails(
        video_id=str(video_id),
        title=case["title"],
        niche=niche,
        turning_point=tp,
        prompts=seo.thumbnail_prompts,
    )

    checklist = {
        "video_path": video.get("assembled_video_path"),
        "subtitle_path": video.get("subtitle_path"),
        "suggested_title": main_title,
        "viral_titles": seo.viral_titles,
        "suggested_description": seo.description,
        "tags": seo.tags,
        "hashtags": seo.hashtags,
        "thumbnail_paths": thumbnail_paths,
    }

    db.update_video(video_id, title=main_title)
    db.record_agent_run(
        video_id,
        "publishing",
        "succeeded",
        input={"video_id": video_id, "action": "regenerate_seo"},
        output=checklist,
    )
    return RedirectResponse(f"/videos/{video_id}", status_code=303)


@app.post("/videos/{video_id}/shorts")
def make_short(video_id: str):
    runner.start_short(video_id)
    return RedirectResponse(f"/videos/{video_id}", status_code=303)


@app.post("/videos/{video_id}/publish")
def publish(video_id: str, youtube_ref: str = Form(...)):
    mark_published(video_id, youtube_ref)
    return RedirectResponse(f"/videos/{video_id}", status_code=303)


@app.get("/media/{video_id}/{path:path}")
def media(video_id: str, path: str):
    # video_id isn't trusted for path construction beyond this one join —
    # anything that escapes MEDIA_DIR via ".." 404s because the resolved
    # path is checked against the media root below.
    full_path = (MEDIA_DIR / video_id / path).resolve()
    media_root = MEDIA_DIR.resolve()
    if media_root not in full_path.parents or not full_path.is_file():
        return RedirectResponse("/", status_code=303)
    return FileResponse(full_path)
