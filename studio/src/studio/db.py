"""Thin Postgres connection helper. No ORM — the schema is small enough
(db/schema.sql) that raw SQL via psycopg is more legible than an ORM layer.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from pgvector.psycopg import register_vector
from psycopg import Connection
from psycopg.rows import dict_row

from studio.config import settings

# IDs cross the LangGraph state boundary as plain str (PipelineState fields
# are str for easy serialization) but come back from psycopg as UUID —
# every function below that takes an id accepts either.
Id = UUID | str


def _json_default(value: Any) -> Any:
    """Postgres `numeric` columns (e.g. cases.score) come back as Decimal,
    which json.dumps doesn't know how to serialize."""
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


@contextmanager
def get_connection() -> Iterator[Connection[dict[str, Any]]]:
    conn = psycopg.connect(settings.database_url, row_factory=dict_row)
    try:
        register_vector(conn)
    except psycopg.ProgrammingError:
        # `vector` extension doesn't exist yet — true only on the very first
        # connection init_db.py makes, which is the one that creates it.
        # Nothing on that connection touches a vector column, so proceeding
        # without the type adapter registered is safe.
        conn.rollback()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# --- users & authentication ------------------------------------------


def create_user(
    email: str,
    password_hash: str,
    full_name: str = "",
    is_admin: bool = False,
) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            insert into users (email, password_hash, full_name, is_admin)
            values (%s, %s, %s, %s)
            returning id, email, full_name, is_admin, settings, created_at
            """,
            (email.lower().strip(), password_hash, full_name.strip(), is_admin),
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to create user")
        return dict(row)


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "select id, email, password_hash, full_name, is_admin, settings, created_at from users where email = %s",
            (email.lower().strip(),),
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: Id) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "select id, email, password_hash, full_name, is_admin, settings, created_at from users where id = %s",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def list_users(limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            select id, email, full_name, is_admin, settings, created_at
            from users
            order by created_at desc
            limit %s
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def count_users() -> int:
    with get_connection() as conn:
        row = conn.execute("select count(*) as c from users").fetchone()
        return int(row["c"]) if row else 0


def delete_user(user_id: Id) -> None:
    with get_connection() as conn:
        conn.execute("delete from users where id = %s", (user_id,))


def toggle_user_admin(user_id: Id) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "update users set is_admin = not is_admin where id = %s returning is_admin",
            (user_id,),
        ).fetchone()
        return bool(row["is_admin"]) if row else False


def get_admin_stats() -> dict[str, Any]:
    with get_connection() as conn:
        u_count = conn.execute("select count(*) as c from users").fetchone()["c"]
        v_count = conn.execute("select count(*) as c from videos").fetchone()["c"]
        pub_count = conn.execute("select count(*) as c from videos where status = 'published'").fetchone()["c"]
        runs_count = conn.execute("select count(*) as c from agent_runs").fetchone()["c"]
        shorts_count = conn.execute("select count(*) as c from agent_runs where agent_name = 'shorts_assembly' and status = 'succeeded'").fetchone()["c"]
        cases_count = conn.execute("select count(*) as c from cases").fetchone()["c"]
        return {
            "total_users": int(u_count),
            "total_videos": int(v_count),
            "total_published": int(pub_count),
            "total_runs": int(runs_count),
            "total_shorts": int(shorts_count),
            "total_cases": int(cases_count),
        }


def update_user_profile(
    user_id: Id,
    full_name: str,
    email: str,
    password_hash: str | None = None,
) -> None:
    with get_connection() as conn:
        if password_hash:
            conn.execute(
                "update users set full_name = %s, email = %s, password_hash = %s where id = %s",
                (full_name.strip(), email.lower().strip(), password_hash, user_id),
            )
        else:
            conn.execute(
                "update users set full_name = %s, email = %s where id = %s",
                (full_name.strip(), email.lower().strip(), user_id),
            )


def update_user_settings(user_id: Id, user_settings: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            "update users set settings = %s::jsonb where id = %s",
            (json.dumps(user_settings), user_id),
        )


def ensure_default_user() -> dict[str, Any]:
    from studio.tools.auth import hash_password

    user = get_user_by_email("admin@studio.ai")
    if user:
        if not user.get("is_admin"):
            with get_connection() as conn:
                conn.execute("update users set is_admin = true where id = %s", (user["id"],))
            user["is_admin"] = True
        return user
    return create_user("admin@studio.ai", hash_password("admin123"), "Studio Admin", is_admin=True)


# --- channels ---------------------------------------------------------


def get_channel_id(name: str) -> UUID:
    with get_connection() as conn:
        row = conn.execute("select id from channels where name = %s", (name,)).fetchone()
    if row is None:
        raise RuntimeError(f"No channel named {name!r} — run scripts/init_db.py first")
    return row["id"]


# --- cases (Case Sourcing backlog) -------------------------------------


def upsert_case(
    channel_id: Id,
    title: str,
    jurisdiction: str,
    era: str,
    turning_point: str,
    score: float,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            insert into cases (channel_id, title, jurisdiction, era, turning_point, score)
            select %s, %s, %s, %s, %s, %s
            where not exists (
                select 1 from cases where channel_id = %s and title = %s
            )
            """,
            (channel_id, title, jurisdiction, era, turning_point, score, channel_id, title),
        )


def get_case_by_title(channel_id: Id, title: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            select id, title, jurisdiction, era, turning_point, score
            from cases
            where channel_id = %s and title = %s
            """,
            (channel_id, title),
        ).fetchone()
    return dict(row) if row else None


def get_top_candidate_case(channel_id: Id) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            select id, title, jurisdiction, era, turning_point, score
            from cases
            where channel_id = %s and status = 'candidate'
            order by score desc
            limit 1
            """,
            (channel_id,),
        ).fetchone()
    return dict(row) if row else None


def list_backlog(channel_id: Id, limit: int = 50) -> list[dict[str, Any]]:
    """Unselected candidates, highest-scored first — same ordering
    get_top_candidate_case uses, just not limited to one row. Powers
    web/app.py's backlog view."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            select id, title, jurisdiction, era, turning_point, score
            from cases
            where channel_id = %s and status = 'candidate'
            order by score desc
            limit %s
            """,
            (channel_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def count_backlog(channel_id: Id) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "select count(*) as n from cases where channel_id = %s and status = 'candidate'",
            (channel_id,),
        ).fetchone()
    assert row is not None, "count(*) always returns exactly one row"
    return row["n"]


def mark_case_selected(case_id: Id) -> None:
    with get_connection() as conn:
        conn.execute("update cases set status = 'selected' where id = %s", (case_id,))


def get_case(case_id: Id) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("select * from cases where id = %s", (case_id,)).fetchone()
    if row is None:
        raise RuntimeError(f"No case with id {case_id}")
    return dict(row)


# --- videos --------------------------------------------------------------


def create_video_for_case(case_id: Id, channel_id: Id, title: str) -> UUID:
    with get_connection() as conn:
        row = conn.execute(
            """
            insert into videos (channel_id, case_id, title, status)
            values (%s, %s, %s, 'sourced')
            returning id
            """,
            (channel_id, case_id, title),
        ).fetchone()
    assert row is not None, "INSERT ... RETURNING always yields a row on success"
    return row["id"]


def get_video(video_id: Id) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("select * from videos where id = %s", (video_id,)).fetchone()
    if row is None:
        raise RuntimeError(f"No video with id {video_id}")
    return dict(row)


def list_videos(limit: int = 50) -> list[dict[str, Any]]:
    """Most recently created videos first, with the case title joined in —
    powers web/app.py's dashboard and library views."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            select v.id, v.title, v.status, v.created_at, v.updated_at,
                   v.assembled_video_path, v.youtube_video_id, c.title as case_title
            from videos v
            left join cases c on c.id = v.case_id
            order by v.created_at desc
            limit %s
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_agent_runs(video_id: Id) -> list[dict[str, Any]]:
    """Every agent_runs row for a video, oldest first — the full per-stage
    history, including retries (an agent that failed then succeeded shows
    up twice, on purpose). scripts/status.py prints this; resume's
    get_latest_agent_output (below) reads a filtered, single-row slice of
    the same table."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            select agent_name, status, error, started_at, finished_at
            from agent_runs
            where video_id = %s
            order by started_at
            """,
            (video_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_video(video_id: Id, **fields: Any) -> None:
    """Column names come from **kwargs, always literal keyword arguments at
    the call site (e.g. `status="rejected"`), never a dict built from
    external input — that's what makes building the SET clause from dict
    keys safe despite the noqa below. Keep it that way: never call this
    with `**some_external_dict`."""
    if not fields:
        return
    set_clause = ", ".join(f"{key} = %s" for key in fields)
    with get_connection() as conn:
        conn.execute(
            f"update videos set {set_clause}, updated_at = now() where id = %s",  # noqa: S608
            (*fields.values(), video_id),
        )


# --- angle embeddings (Originality & Angle corpus) ------------------------


def find_similar_angles(
    channel_id: Id, embedding: list[float], limit: int = 3
) -> list[dict[str, Any]]:
    """Cosine similarity, most similar first. `<=>` is pgvector's cosine
    *distance* operator (0 = identical), so similarity = 1 - distance."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            select video_id, text_embedded, 1 - (embedding <=> %s::vector) as similarity
            from angle_embeddings
            where channel_id = %s
            order by embedding <=> %s::vector
            limit %s
            """,
            (embedding, channel_id, embedding, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def record_angle_embedding(
    channel_id: Id, video_id: Id, case_id: Id, text_embedded: str, embedding: list[float]
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            insert into angle_embeddings (channel_id, video_id, case_id, text_embedded, embedding)
            values (%s, %s, %s, %s, %s::vector)
            """,
            (channel_id, video_id, case_id, text_embedded, embedding),
        )


# --- agent run / decision audit trail ------------------------------------


def record_agent_run(
    video_id: Id,
    agent_name: str,
    status: str,
    input: dict[str, Any] | None = None,  # noqa: A002
    output: dict[str, Any] | None = None,
    error: str | None = None,
) -> UUID:
    with get_connection() as conn:
        row = conn.execute(
            """
            insert into agent_runs (video_id, agent_name, status, input, output, error, finished_at)
            values (%s, %s, %s, %s, %s, %s, now())
            returning id
            """,
            (
                video_id,
                agent_name,
                status,
                json.dumps(input, default=_json_default) if input is not None else None,
                json.dumps(output, default=_json_default) if output is not None else None,
                error,
            ),
        ).fetchone()
    assert row is not None, "INSERT ... RETURNING always yields a row on success"
    return row["id"]


def get_latest_agent_output(video_id: Id, agent_name: str) -> dict[str, Any] | None:
    """Most recent *succeeded* run's output for a given agent on a given
    video, or None if it never succeeded — used by scripts/run_pipeline.py
    to resume a video from the first stage that hasn't actually completed,
    reusing what's already in the DB instead of re-running it. A stage that
    only ever `failed` correctly falls through to None here (get retried),
    not treated as done."""
    with get_connection() as conn:
        row = conn.execute(
            """
            select output from agent_runs
            where video_id = %s and agent_name = %s and status = 'succeeded'
            order by started_at desc
            limit 1
            """,
            (video_id, agent_name),
        ).fetchone()
    return row["output"] if row else None


def record_decision(
    video_id: Id,
    agent_name: str,
    decision: str,
    rationale: str,
    confidence: float | None = None,
) -> UUID:
    """The editorial/compliance audit trail (blueprint.md Section 4.5,
    4.6): evidence of a real decision process, not just "the model said it
    was fine". First actually written to on Day 6 (Quality Review,
    Compliance) — the table has existed since Day 1's schema but nothing
    used it until there was a real editorial decision to record."""
    with get_connection() as conn:
        row = conn.execute(
            """
            insert into decisions (video_id, agent_name, decision, rationale, confidence)
            values (%s, %s, %s, %s, %s)
            returning id
            """,
            (video_id, agent_name, decision, rationale, confidence),
        ).fetchone()
    assert row is not None, "INSERT ... RETURNING always yields a row on success"
    return row["id"]
