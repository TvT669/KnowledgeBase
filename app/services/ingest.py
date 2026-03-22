from __future__ import annotations

import hashlib
import sqlite3
from typing import Optional

from app.db import get_conn


def insert_message(
    source: str,
    role: str,
    content: str,
    summary: str,
    session_id: Optional[str] = None,
) -> tuple[bool, int | None]:
    """
    Returns (inserted, row_id). inserted=False means deduplicated.
    """
    content_hash = hashlib.sha256(
        f"{source}|{session_id}|{role}|{content}".encode("utf-8")
    ).hexdigest()

    with get_conn() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO messages(source, session_id, role, content, content_hash, summary)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (source, session_id, role, content, content_hash, summary),
            )
            return True, cur.lastrowid
        except sqlite3.IntegrityError:
            return False, None
