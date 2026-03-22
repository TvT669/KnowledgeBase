from __future__ import annotations

from typing import Any

from app.db import get_conn


def search_messages(query: str, limit: int = 10) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.source, m.session_id, m.role, m.content, m.created_at, m.summary
            FROM messages_fts f
            JOIN messages m ON m.id = f.rowid
            WHERE messages_fts MATCH ?
            ORDER BY bm25(messages_fts)
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()

        # Fallback for CJK text when FTS tokenization misses short keywords.
        if not rows:
            tokens = [t for t in query.replace("OR", " ").split() if t]
            if tokens:
                where_clause = " OR ".join(["content LIKE ?", "summary LIKE ?"] * len(tokens))
                args = []
                for token in tokens:
                    like_token = f"%{token}%"
                    args.extend([like_token, like_token])
                args.append(limit)
                rows = conn.execute(
                    f"""
                    SELECT id, source, session_id, role, content, created_at, summary
                    FROM messages
                    WHERE {where_clause}
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    tuple(args),
                ).fetchall()

    return [dict(r) for r in rows]


def latest_messages(limit: int = 30) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, source, session_id, role, content, created_at, summary
            FROM messages
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(r) for r in rows]
