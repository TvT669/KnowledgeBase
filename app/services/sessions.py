from __future__ import annotations

from typing import Any

from app.db import get_conn


def latest_sessions(limit: int = 12) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            WITH grouped AS (
                SELECT
                    source,
                    session_id,
                    COUNT(*) AS message_count,
                    MAX(id) AS latest_id
                FROM messages
                WHERE COALESCE(session_id, '') <> ''
                GROUP BY source, session_id
                ORDER BY latest_id DESC
                LIMIT ?
            )
            SELECT
                g.source,
                g.session_id,
                g.message_count,
                g.latest_id,
                m.created_at AS latest_created_at,
                COALESCE(NULLIF(m.summary, ''), substr(m.content, 1, 160)) AS latest_summary
            FROM grouped g
            JOIN messages m ON m.id = g.latest_id
            ORDER BY g.latest_id DESC
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_session_messages(source: str, session_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, source, session_id, role, content, created_at, summary
            FROM messages
            WHERE source = ? AND session_id = ?
            ORDER BY id ASC
            """,
            (source, session_id),
        ).fetchall()

    return [dict(row) for row in rows]
