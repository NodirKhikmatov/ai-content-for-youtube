"""Thin Postgres connection helper. No ORM — the schema is small enough
(db/schema.sql) that raw SQL via psycopg is more legible than an ORM layer.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection

from studio.config import settings


@contextmanager
def get_connection() -> Iterator[Connection]:
    conn = psycopg.connect(settings.database_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
