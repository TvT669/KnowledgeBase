from __future__ import annotations

from typing import Any

from app.db import get_conn


NOTE_SELECT = """
    SELECT
        n.id,
        n.title,
        n.problem,
        n.root_cause,
        n.solution,
        n.key_takeaways,
        n.status,
        n.source_type,
        n.created_at,
        n.updated_at,
        COUNT(ns.message_id) AS source_count,
        COALESCE(GROUP_CONCAT(DISTINCT m.source), '') AS source_labels
    FROM notes n
    LEFT JOIN note_sources ns ON ns.note_id = n.id
    LEFT JOIN messages m ON m.id = ns.message_id
"""


def _normalize_note_row(row: Any) -> dict[str, Any]:
    note = dict(row)
    labels = (note.get("source_labels") or "").split(",")
    note["source_labels"] = [label.strip() for label in labels if label and label.strip()]
    note["source_count"] = int(note.get("source_count") or 0)
    return note


def get_messages_by_ids(message_ids: list[int]) -> list[dict[str, Any]]:
    if not message_ids:
        return []

    placeholders = ",".join("?" for _ in message_ids)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT id, source, session_id, role, content, created_at, summary
            FROM messages
            WHERE id IN ({placeholders})
            """,
            tuple(message_ids),
        ).fetchall()

    by_id = {row["id"]: dict(row) for row in rows}
    return [by_id[message_id] for message_id in message_ids if message_id in by_id]


def create_note(
    *,
    title: str,
    problem: str,
    root_cause: str,
    solution: str,
    key_takeaways: str,
    message_ids: list[int],
    status: str = "draft",
    source_type: str = "mixed",
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO notes(title, problem, root_cause, solution, key_takeaways, status, source_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, problem, root_cause, solution, key_takeaways, status, source_type),
        )
        note_id = int(cur.lastrowid)
        conn.executemany(
            """
            INSERT INTO note_sources(note_id, message_id, sort_order)
            VALUES (?, ?, ?)
            """,
            [(note_id, message_id, index) for index, message_id in enumerate(message_ids)],
        )

    return get_note(note_id)


def update_note(
    note_id: int,
    *,
    title: str,
    problem: str,
    root_cause: str,
    solution: str,
    key_takeaways: str,
    status: str = "draft",
    source_type: str = "mixed",
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE notes
            SET
                title = ?,
                problem = ?,
                root_cause = ?,
                solution = ?,
                key_takeaways = ?,
                status = ?,
                source_type = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                title,
                problem,
                root_cause,
                solution,
                key_takeaways,
                status,
                source_type,
                note_id,
            ),
        )

    if cur.rowcount == 0:
        raise KeyError(note_id)

    return get_note(note_id)


def get_note(note_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            f"""
            {NOTE_SELECT}
            WHERE n.id = ?
            GROUP BY n.id
            """,
            (note_id,),
        ).fetchone()

    if row is None:
        raise KeyError(note_id)

    return _normalize_note_row(row)


def latest_notes(limit: int = 30) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            {NOTE_SELECT}
            GROUP BY n.id
            ORDER BY n.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_normalize_note_row(row) for row in rows]


def search_notes(query: str, limit: int = 20) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            WITH matched AS (
                SELECT rowid AS note_id, bm25(notes_fts) AS rank
                FROM notes_fts
                WHERE notes_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            )
            SELECT
                n.id,
                n.title,
                n.problem,
                n.root_cause,
                n.solution,
                n.key_takeaways,
                n.status,
                n.source_type,
                n.created_at,
                n.updated_at,
                COUNT(ns.message_id) AS source_count,
                COALESCE(GROUP_CONCAT(DISTINCT m.source), '') AS source_labels
            FROM matched
            JOIN notes n ON n.id = matched.note_id
            LEFT JOIN note_sources ns ON ns.note_id = n.id
            LEFT JOIN messages m ON m.id = ns.message_id
            GROUP BY n.id
            ORDER BY MIN(matched.rank), n.id DESC
            """,
            (query, limit),
        ).fetchall()

        if not rows:
            tokens = [t for t in query.replace("OR", " ").split() if t]
            if tokens:
                where_clause = " OR ".join(
                    ["n.title LIKE ?", "n.problem LIKE ?", "n.root_cause LIKE ?", "n.solution LIKE ?", "n.key_takeaways LIKE ?"]
                    * len(tokens)
                )
                args: list[Any] = []
                for token in tokens:
                    like = f"%{token}%"
                    args.extend([like, like, like, like, like])
                args.append(limit)
                rows = conn.execute(
                    f"""
                    {NOTE_SELECT}
                    WHERE {where_clause}
                    GROUP BY n.id
                    ORDER BY n.id DESC
                    LIMIT ?
                    """,
                    tuple(args),
                ).fetchall()

    return [_normalize_note_row(row) for row in rows]


def get_note_sources(note_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                m.id,
                m.source,
                m.session_id,
                m.role,
                m.content,
                m.created_at,
                m.summary,
                ns.sort_order
            FROM note_sources ns
            JOIN messages m ON m.id = ns.message_id
            WHERE ns.note_id = ?
            ORDER BY ns.sort_order ASC, m.id ASC
            """,
            (note_id,),
        ).fetchall()

    return [dict(row) for row in rows]
