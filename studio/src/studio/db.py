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


def update_video(video_id: Id, **fields: Any) -> None:
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
