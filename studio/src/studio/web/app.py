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
from studio.tools.auth import (
    create_session_token,
    hash_password,
    verify_password,
    verify_session_token,
)
from studio.web import runner

app = FastAPI(title="The Turning Point — Studio")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
CHANNEL_NAME = "The Turning Point"
MEDIA_DIR = Path("media")


def _get_current_user(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get("session_token")
    if token:
        user_id = verify_session_token(token)
        if user_id:
            user = db.get_user_by_id(user_id)
            if user:
                return user
    return db.ensure_default_user()


def _render(request: Request, template_name: str, context: dict[str, Any]):
    context["current_user"] = _get_current_user(request)
    return templates.TemplateResponse(request, template_name, context)


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


# --- Authentication Routes -------------------------------------------


@app.get("/login")
def login_page(request: Request, error: str | None = None):
    return _render(request, "login.html", {"error": error})


@app.post("/login")
def handle_login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = db.get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        return _render(
            request, "login.html", {"error": "Invalid email or password", "email": email}
        )
    token = create_session_token(str(user["id"]))
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("session_token", token, max_age=30 * 24 * 3600, httponly=True)
    return response


@app.get("/register")
def register_page(request: Request, error: str | None = None):
    return _render(request, "register.html", {"error": error})


@app.post("/register")
def handle_register(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    if len(password) < 6:
        return _render(
            request, "register.html", {"error": "Password must be at least 6 characters"}
        )
    existing = db.get_user_by_email(email)
    if existing:
        return _render(
            request, "register.html", {"error": "An account with this email already exists"}
        )
    user = db.create_user(email, hash_password(password), full_name)
    token = create_session_token(str(user["id"]))
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("session_token", token, max_age=30 * 24 * 3600, httponly=True)
    return response


@app.get("/logout")
def handle_logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session_token")
    return response


@app.get("/profile")
def profile_page(request: Request, saved: bool = False, error: str | None = None):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return _render(request, "profile.html", {"user": user, "saved": saved, "error": error})


@app.post("/profile")
def handle_update_profile(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    new_password: str = Form(""),
    anthropic_api_key: str = Form(""),
    elevenlabs_api_key: str = Form(""),
    kling_access_key: str = Form(""),
    kling_secret_key: str = Form(""),
    gemini_api_key: str = Form(""),
    tavily_api_key: str = Form(""),
):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    pw_hash = hash_password(new_password) if new_password.strip() else None
    db.update_user_profile(user["id"], full_name, email, pw_hash)

    personal_settings = dict(user.get("settings") or {})
    personal_settings.update(
        {
            "anthropic_api_key": anthropic_api_key.strip(),
            "elevenlabs_api_key": elevenlabs_api_key.strip(),
            "kling_access_key": kling_access_key.strip(),
            "kling_secret_key": kling_secret_key.strip(),
            "gemini_api_key": gemini_api_key.strip(),
            "tavily_api_key": tavily_api_key.strip(),
        }
    )
    db.update_user_settings(user["id"], personal_settings)

    return RedirectResponse("/profile?saved=true", status_code=303)


# --- Admin SuperUser Routes ------------------------------------------


@app.get("/admin")
def admin_dashboard(request: Request):
    user = _get_current_user(request)
    if not user or not user.get("is_admin"):
        return RedirectResponse("/login", status_code=303)

    stats = db.get_admin_stats()
    users = db.list_users(limit=200)
    recent_videos = db.list_videos(limit=20)

    context = {
        "stats": stats,
        "users": users,
        "recent_videos": recent_videos,
        "settings": settings,
    }
    return _render(request, "admin.html", context)


@app.post("/admin/users/{user_id}/toggle_admin")
def handle_toggle_admin(request: Request, user_id: str):
    user = _get_current_user(request)
    if not user or not user.get("is_admin"):
        return RedirectResponse("/login", status_code=303)
    db.toggle_user_admin(user_id)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/users/{user_id}/delete")
def handle_delete_user(request: Request, user_id: str):
    user = _get_current_user(request)
    if not user or not user.get("is_admin"):
        return RedirectResponse("/login", status_code=303)
    # Prevent deleting own account
    if str(user["id"]) != str(user_id):
        db.delete_user(user_id)
    return RedirectResponse("/admin", status_code=303)



# --- Content Calendar Routes -----------------------------------------


@app.get("/calendar")
def calendar_page(request: Request):
    channel_id = _channel_id()
    entries = db.list_calendar(channel_id)
    return _render(request, "calendar.html", {"entries": entries})


@app.post("/calendar/generate")
def generate_calendar(request: Request):
    from studio.agents.content_calendar import generate_content_calendar
    channel_id = _channel_id()
    # Pass existing cases as context to avoid duplicates
    existing_cases = [c["title"] for c in db.list_backlog(channel_id, limit=50)]
    entries = generate_content_calendar(
        channel_niche=settings.channel_niche if hasattr(settings, "channel_niche") else "True Crime & Justice",
        format_thesis="The single turning point that changed everything",
        existing_cases=existing_cases,
    )
    db.save_calendar(channel_id, entries)
    return RedirectResponse("/calendar", status_code=303)


@app.post("/calendar/{entry_id}/produce")
def calendar_produce(request: Request, entry_id: str):
    """Start a new pipeline run from a calendar entry."""
    channel_id = _channel_id()
    entries = db.list_calendar(channel_id)
    entry = next((e for e in entries if str(e["id"]) == entry_id), None)
    if entry:
        custom_topic = {
            "title": entry["title"],
            "niche": entry.get("content_type", "documentary"),
            "turning_point": entry.get("turning_point") or "",
            "extra_context": entry.get("hook") or "",
        }
        handle = runner.start_run(custom_topic=custom_topic)
        db.update_calendar_entry_status(entry_id, "in_progress")
        return RedirectResponse(f"/runs/{handle.thread_id}", status_code=303)
    return RedirectResponse("/calendar", status_code=303)


@app.post("/calendar/{entry_id}/skip")
def calendar_skip(entry_id: str):
    db.update_calendar_entry_status(entry_id, "skipped")
    return RedirectResponse("/calendar", status_code=303)


@app.post("/calendar/{entry_id}/restore")
def calendar_restore(entry_id: str):
    db.update_calendar_entry_status(entry_id, "planned")
    return RedirectResponse("/calendar", status_code=303)


# --- Studio Dashboard & Routes ---------------------------------------


@app.get("/landing")
def landing_page(request: Request):
    return templates.TemplateResponse(request, "landing.html", {})


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
    return _render(request, "index.html", context)


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
        return _render(
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
    return _render(request, "run_status.html", context)


@app.post("/runs/{thread_id}/decide")
def decide(thread_id: str, decision: str = Form(...), notes: str = Form("")):
    runner.submit_decision(thread_id, decision, notes)
    return RedirectResponse(f"/runs/{thread_id}", status_code=303)


from studio.config import settings, update_settings


@app.get("/create")
def create_page(request: Request):
    return _render(request, "create.html", {})


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
    return _render(request, "settings.html", context)


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
    bgm_enabled: str = Form("true"),
    bgm_volume: float = Form(0.15),
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
        bgm_enabled=bgm_enabled.lower() == "true",
        bgm_volume=bgm_volume,
    )
    return RedirectResponse("/settings?saved=true", status_code=303)


@app.get("/backlog")
def backlog(request: Request):
    channel_id = _channel_id()
    context = {"cases": db.list_backlog(channel_id, limit=100)}
    return _render(request, "backlog.html", context)


@app.get("/videos")
def videos(request: Request):
    context = {"videos": db.list_videos(limit=200)}
    return _render(request, "videos.html", context)


@app.get("/videos/{video_id}")
def video_detail(request: Request, video_id: str):
    video = db.get_video(video_id)
    agent_runs = db.get_agent_runs(video_id)
    beat_sheet = db.get_latest_agent_output(video_id, "storytelling")
    quality_verdict = db.get_latest_agent_output(video_id, "quality_review")
    compliance_verdict = db.get_latest_agent_output(video_id, "compliance")
    publishing_output = db.get_latest_agent_output(video_id, "publishing") or {}
    short_output = db.get_latest_agent_output(video_id, "shorts_assembly") or {}
    short_handle = runner.SHORTS.get(video_id)
    thumb_paths = publishing_output.get("thumbnail_paths", [])
    thumb_media_urls = [f"/media/{video_id}/thumbnails/thumbnail_{i + 1}.jpg" for i in range(len(thumb_paths))]

    # Find all dubbed language versions
    dubbed_versions = []
    for r in agent_runs:
        if r["agent_name"].startswith("dubbing_") and r["status"] == "succeeded" and r.get("output"):
            out = r["output"]
            dubbed_versions.append({
                "lang_code": out.get("target_lang"),
                "lang_name": out.get("lang_name"),
                "translated_title": out.get("translated_title"),
                "translated_narration": out.get("translated_narration"),
                "media_rel": _media_rel(out.get("final_path"), video_id),
                "duration_seconds": out.get("duration_seconds", 0),
            })

    from studio.agents.dubbing import SUPPORTED_LANGUAGES

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
        "dubbed_versions": dubbed_versions,
        "supported_languages": SUPPORTED_LANGUAGES,
        "min_dimension_score": MIN_DIMENSION_SCORE,
        "assembled_media_rel": _media_rel(video.get("assembled_video_path"), video_id),
        "short_media_rel": _media_rel(
            short_output.get("final_path") if short_output else None, video_id
        ),
    }
    return _render(request, "video_detail.html", context)


@app.post("/videos/{video_id}/dub")
def handle_dub_video(video_id: str, target_lang: str = Form("uz")):
    from studio.agents.dubbing import dub_video
    dub_video(video_id, target_lang)
    return RedirectResponse(f"/videos/{video_id}", status_code=303)


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


from studio.tools.youtube_upload import upload_video_to_youtube


@app.post("/videos/{video_id}/publish_api")
def publish_api(
    video_id: str,
    selected_title: str = Form(""),
    privacy_status: str = Form("unlisted"),
    thumbnail_idx: int = Form(1),
):
    video = db.get_video(video_id)
    publishing_output = db.get_latest_agent_output(video_id, "publishing") or {}

    title = selected_title.strip() or video.get("title") or "YouTube Video"
    description = publishing_output.get("suggested_description") or ""
    tags = publishing_output.get("tags") or []

    thumb_paths = publishing_output.get("thumbnail_paths") or []
    thumb_path = (
        Path(thumb_paths[thumbnail_idx - 1])
        if 0 < thumbnail_idx <= len(thumb_paths)
        else None
    )

    assembled_path = Path(
        video.get("assembled_video_path") or (MEDIA_DIR / video_id / "assembled.mp4")
    )

    res = upload_video_to_youtube(
        video_path=assembled_path,
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy_status,
        thumbnail_path=thumb_path,
    )

    yt_id = res.get("youtube_video_id", "sim_yt_live")
    mark_published(video_id, yt_id)
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
