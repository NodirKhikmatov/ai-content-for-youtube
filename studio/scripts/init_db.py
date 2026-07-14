"""Apply db/schema.sql to DATABASE_URL, then seed the one channel row Phase 1
needs. Run after `docker compose up -d`:

    python scripts/init_db.py
"""

from pathlib import Path

from studio.db import get_connection

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def main() -> None:
    schema_sql = SCHEMA_PATH.read_text()
    with get_connection() as conn:
        conn.execute(schema_sql)
        conn.execute(
            """
            insert into channels (name, niche, format_thesis)
            select %s, %s, %s
            where not exists (select 1 from channels where name = %s)
            """,
            (
                "The Turning Point",
                "true crime / closed court cases",
                "Each video reconstructs a closed court case in strict "
                "chronological order from public record, built around the "
                "single piece of evidence, testimony, or decision that "
                "flipped the outcome.",
                "The Turning Point",
            ),
        )
    print(f"Schema applied from {SCHEMA_PATH}, channel seeded.")


if __name__ == "__main__":
    main()
