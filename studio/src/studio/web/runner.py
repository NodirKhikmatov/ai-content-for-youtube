"""In-process background execution for the web dashboard.

LangGraph's Quality Review interrupt()/Command(resume=...) cycle only
works within the single process that started the run (InMemorySaver — see
graph.py's compiled() docstring); scripts/run_pipeline.py works around
that by being one continuous CLI invocation that blocks on terminal
input(). The web server sidesteps the same constraint differently: it
stays alive as a long-running process, so one shared compiled() graph
gives every run in this process the same single-process guarantee that
CLI invocation relies on — just driven by HTTP requests (start / decide)
instead of blocking on stdin, with each run's actual work happening on a
background thread so request handlers return immediately.
"""

import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langgraph.types import Command

from studio.graph import compiled
from studio.resume import build_resume_state
from studio.shorts import make_short_video

log = logging.getLogger(__name__)

_PIPELINE = compiled()  # one shared graph + InMemorySaver for the server's lifetime


@dataclass
class RunHandle:
    thread_id: str
    resumed_from: str | None = None
    status: str = "running"  # running | paused | finished | failed
    video_id: str | None = None
    case_id: str | None = None
    interrupt_payload: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


RUNS: dict[str, RunHandle] = {}


@dataclass
class ShortHandle:
    video_id: str
    status: str = "running"  # running | finished | failed
    output: dict[str, Any] | None = None
    error: str | None = None


SHORTS: dict[str, ShortHandle] = {}


def _apply_result(handle: RunHandle, result: dict[str, Any]) -> None:
    with handle.lock:
        handle.video_id = result.get("video_id") or handle.video_id
        handle.case_id = result.get("case_id") or handle.case_id
        if "__interrupt__" in result:
            handle.status = "paused"
            handle.interrupt_payload = result["__interrupt__"][0].value
        else:
            handle.status = "finished"
            handle.result = result


def _run_thread(handle: RunHandle, invoke: Callable[[], dict[str, Any]]) -> None:
    try:
        _apply_result(handle, invoke())
    except Exception as exc:
        log.exception("pipeline run %s failed", handle.thread_id)
        with handle.lock:
            handle.status = "failed"
            handle.error = str(exc)


def start_run(
    resume_video_id: str | None = None,
    case_id: str | None = None,
    custom_topic: dict[str, Any] | None = None,
) -> RunHandle:
    thread_id = str(uuid.uuid4())
    handle = RunHandle(thread_id=thread_id, resumed_from=resume_video_id)
    if resume_video_id:
        handle.video_id = resume_video_id
    if case_id:
        handle.case_id = case_id
    RUNS[thread_id] = handle

    config = {"configurable": {"thread_id": thread_id}}
    if resume_video_id:
        initial_state = build_resume_state(resume_video_id)
    elif custom_topic:
        initial_state = {"custom_topic": custom_topic}
    elif case_id:
        initial_state = {"case_id": case_id}
    else:
        initial_state = {}

    threading.Thread(
        target=_run_thread,
        args=(handle, lambda: _PIPELINE.invoke(initial_state, config=config)),
        daemon=True,
    ).start()
    return handle


def submit_decision(thread_id: str, decision: str, notes: str) -> RunHandle:
    handle = RUNS[thread_id]
    with handle.lock:
        handle.status = "running"
        handle.interrupt_payload = None

    config = {"configurable": {"thread_id": thread_id}}
    threading.Thread(
        target=_run_thread,
        args=(
            handle,
            lambda: _PIPELINE.invoke(
                Command(resume={"decision": decision, "notes": notes}), config=config
            ),
        ),
        daemon=True,
    ).start()
    return handle


def active_runs() -> list[RunHandle]:
    return [h for h in RUNS.values() if h.status in ("running", "paused")]


def _short_thread(handle: ShortHandle) -> None:
    try:
        handle.output = make_short_video(handle.video_id)
        handle.status = "finished"
    except Exception as exc:
        log.exception("shorts run for %s failed", handle.video_id)
        handle.status = "failed"
        handle.error = str(exc)


def start_short(video_id: str) -> ShortHandle:
    handle = ShortHandle(video_id=video_id)
    SHORTS[video_id] = handle
    threading.Thread(target=_short_thread, args=(handle,), daemon=True).start()
    return handle
