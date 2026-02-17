import sqlite3
from dataclasses import dataclass


@dataclass
class EmailEventRow:
    message_id: str
    from_email: str | None
    subject: str | None
    received_at: str | None
    snippet: str | None
    category: str


def insert_email_event(conn: sqlite3.Connection, row: EmailEventRow) -> bool:
    """
    Insert one email event. Returns True if inserted, False if duplicate (message_id exists).
    """
    try:
        conn.execute(
            """
            INSERT INTO email_events (message_id, from_email, subject, received_at, snippet, category)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row.message_id,
                row.from_email,
                row.subject,
                row.received_at,
                row.snippet,
                row.category,
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # UNIQUE constraint failed: email_events.message_id
        return False


def list_email_events(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, message_id, from_email, subject, received_at, category, created_at
        FROM email_events
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
