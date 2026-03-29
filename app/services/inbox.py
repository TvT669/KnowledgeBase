from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from app.db import get_conn
from app.services.sessions import _build_session_insight, get_session_messages, latest_sessions


STATUS_LABELS = {
    "ready": "建议先整理",
    "new": "待判断",
    "later": "稍后处理",
    "ignored": "已忽略",
    "done": "最近完成",
}


def _utc_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _parse_tags(raw: Any) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _priority_rank(label: str) -> int:
    if "推荐" in label:
        return 2
    if "值得" in label:
        return 1
    return 0


def _estimate_confidence(session: dict[str, Any]) -> float:
    confidence = 0.35 + min(int(session.get("priority_score") or 0), 6) * 0.08
    if session.get("topic_title") and "待整理" not in str(session["topic_title"]):
        confidence += 0.08
    if session.get("tags"):
        confidence += 0.05
    return round(min(confidence, 0.95), 2)


def _default_status_for_priority(priority_label: str) -> str:
    return "ready" if _priority_rank(priority_label) >= 1 else "new"


def _session_to_payload(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "ai_title": session.get("topic_title") or session.get("session_id") or "待整理会话",
        "ai_excerpt": session.get("topic_excerpt") or session.get("latest_summary") or "",
        "ai_tags_json": json.dumps(session.get("tags") or [], ensure_ascii=False),
        "ai_priority": session.get("priority_label") or "待判断",
        "ai_reason": session.get("priority_reason") or "等待确认",
        "ai_confidence": _estimate_confidence(session),
        "message_count": int(session.get("message_count") or 0),
        "latest_message_id": int(session.get("latest_id") or 0),
        "length_label": session.get("length_label") or "待整理会话",
        "last_seen_at": session.get("latest_created_at") or _utc_now(),
        "default_status": _default_status_for_priority(session.get("priority_label") or ""),
    }


def _normalize_query(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _item_matches_query(item: dict[str, Any], query: str) -> bool:
    if not query:
        return True

    haystack = " ".join(
        str(part or "")
        for part in (
            item.get("source"),
            item.get("session_id"),
            item.get("status_label"),
            item.get("display_title"),
            item.get("display_excerpt"),
            item.get("display_priority"),
            item.get("display_reason"),
            " ".join(item.get("display_tags") or []),
        )
    ).lower()
    return all(token in haystack for token in query.split())


def _load_existing_rows(conn: Any, sessions: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    if not sessions:
        return {}

    clauses = []
    args: list[Any] = []
    for session in sessions:
        clauses.append("(source = ? AND session_id = ?)")
        args.extend([session["source"], session["session_id"]])

    rows = conn.execute(
        f"""
        SELECT *
        FROM session_queue
        WHERE {" OR ".join(clauses)}
        """,
        tuple(args),
    ).fetchall()
    return {(row["source"], row["session_id"]): dict(row) for row in rows}


def _resolve_status(existing: dict[str, Any] | None, payload: dict[str, Any], now: str) -> str:
    default_status = payload["default_status"]
    if existing is None:
        return default_status

    current = str(existing.get("status") or "new")
    latest_changed = int(existing.get("latest_message_id") or 0) != int(payload["latest_message_id"])
    snooze_until = existing.get("snooze_until")

    if current == "ignored":
        return current
    if current == "later":
        if snooze_until and str(snooze_until) <= now:
            return default_status
        return current
    if current == "done":
        return default_status if latest_changed else current
    if current == "ready":
        return current
    if current == "new" and default_status == "ready":
        return "ready"
    return current


def _build_session_from_messages(source: str, session_id: str) -> dict[str, Any]:
    messages = get_session_messages(source, session_id)
    if not messages:
        raise KeyError((source, session_id))

    latest_message = messages[-1]
    insight = _build_session_insight(
        session={
            "latest_summary": latest_message.get("summary") or "",
            "message_count": len(messages),
            "latest_id": latest_message["id"],
        },
        messages=messages,
    )
    return {
        "source": source,
        "session_id": session_id,
        "message_count": len(messages),
        "latest_id": latest_message["id"],
        "latest_created_at": latest_message["created_at"],
        "latest_summary": latest_message.get("summary") or "",
        **insight,
    }


def _upsert_queue_row(
    conn: Any,
    *,
    source: str,
    session_id: str,
    payload: dict[str, Any],
    existing: dict[str, Any] | None,
    status: str,
) -> None:
    now = _utc_now()
    if existing is None:
        conn.execute(
            """
            INSERT INTO session_queue(
                source,
                session_id,
                status,
                ai_title,
                ai_excerpt,
                ai_tags_json,
                ai_priority,
                ai_reason,
                ai_confidence,
                user_tags_json,
                message_count,
                latest_message_id,
                length_label,
                first_seen_at,
                last_seen_at,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source,
                session_id,
                status,
                payload["ai_title"],
                payload["ai_excerpt"],
                payload["ai_tags_json"],
                payload["ai_priority"],
                payload["ai_reason"],
                payload["ai_confidence"],
                "[]",
                payload["message_count"],
                payload["latest_message_id"],
                payload["length_label"],
                now,
                payload["last_seen_at"],
                now,
                now,
            ),
        )
        return

    conn.execute(
        """
        UPDATE session_queue
        SET
            status = ?,
            ai_title = ?,
            ai_excerpt = ?,
            ai_tags_json = ?,
            ai_priority = ?,
            ai_reason = ?,
            ai_confidence = ?,
            message_count = ?,
            latest_message_id = ?,
            length_label = ?,
            last_seen_at = ?,
            updated_at = ?
        WHERE source = ? AND session_id = ?
        """,
        (
            status,
            payload["ai_title"],
            payload["ai_excerpt"],
            payload["ai_tags_json"],
            payload["ai_priority"],
            payload["ai_reason"],
            payload["ai_confidence"],
            payload["message_count"],
            payload["latest_message_id"],
            payload["length_label"],
            payload["last_seen_at"],
            now,
            source,
            session_id,
        ),
    )


def refresh_inbox(limit: int = 120) -> dict[str, int]:
    sessions = latest_sessions(limit=limit)
    now = _utc_now()
    inserted = 0
    updated = 0

    with get_conn() as conn:
        existing_map = _load_existing_rows(conn, sessions)
        for session in sessions:
            key = (session["source"], session["session_id"])
            existing = existing_map.get(key)
            payload = _session_to_payload(session)
            status = _resolve_status(existing, payload, now)
            _upsert_queue_row(
                conn,
                source=session["source"],
                session_id=session["session_id"],
                payload=payload,
                existing=existing,
                status=status,
            )
            if existing is None:
                inserted += 1
            else:
                updated += 1

    return {"scanned": len(sessions), "inserted": inserted, "updated": updated}


def _row_to_item(row: Any) -> dict[str, Any]:
    data = dict(row)
    user_tags = _parse_tags(data.get("user_tags_json"))
    ai_tags = _parse_tags(data.get("ai_tags_json"))
    priority = data.get("user_priority") or data.get("ai_priority") or "待判断"
    title = data.get("user_title") or data.get("ai_title") or data.get("session_id") or "待整理会话"
    tags = user_tags or ai_tags
    return {
        "source": data["source"],
        "session_id": data["session_id"],
        "status": data["status"],
        "status_label": STATUS_LABELS.get(data["status"], data["status"]),
        "display_title": title,
        "display_excerpt": data.get("ai_excerpt") or "",
        "display_tags": tags,
        "display_priority": priority,
        "display_reason": data.get("ai_reason") or "等待确认",
        "message_count": int(data.get("message_count") or 0),
        "latest_message_id": int(data.get("latest_message_id") or 0),
        "latest_created_at": data.get("latest_created_at") or data.get("last_seen_at") or "",
        "length_label": data.get("length_label") or "",
        "snooze_until": data.get("snooze_until"),
        "note_id": data.get("note_id"),
        "ai_confidence": float(data.get("ai_confidence") or 0),
        "has_user_override": bool(data.get("user_title") or user_tags or data.get("user_priority")),
    }


def list_inbox_groups(
    limit_per_group: int = 12,
    include_ignored: bool = False,
    query: str | None = None,
) -> dict[str, Any]:
    with get_conn() as conn:
        ignored_filter = "" if include_ignored else "WHERE q.status <> 'ignored'"
        rows = conn.execute(
            f"""
            SELECT
                q.*,
                m.created_at AS latest_created_at
            FROM session_queue q
            LEFT JOIN messages m ON m.id = q.latest_message_id
            {ignored_filter}
            ORDER BY
                CASE q.status
                    WHEN 'ready' THEN 0
                    WHEN 'new' THEN 1
                    WHEN 'later' THEN 2
                    WHEN 'done' THEN 3
                    ELSE 4
                END,
                CASE COALESCE(q.user_priority, q.ai_priority)
                    WHEN '推荐优先整理' THEN 0
                    WHEN '值得整理' THEN 1
                    WHEN '可稍后整理' THEN 2
                    ELSE 3
                END,
                q.last_seen_at DESC
            """
        ).fetchall()

    groups: dict[str, list[dict[str, Any]]] = {
        "ready": [],
        "new": [],
        "later": [],
        "done": [],
        "ignored": [],
    }
    stats = {
        "pending_count": 0,
        "ready_count": 0,
        "new_count": 0,
        "later_count": 0,
        "done_count": 0,
        "ignored_count": 0,
        "done_this_week": 0,
    }
    week_cutoff = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    normalized_query = _normalize_query(query)

    for row in rows:
        item = _row_to_item(row)
        status = item["status"]
        if status not in groups:
            continue
        if status == "ready":
            stats["ready_count"] += 1
            stats["pending_count"] += 1
        elif status == "new":
            stats["new_count"] += 1
            stats["pending_count"] += 1
        elif status == "later":
            stats["later_count"] += 1
        elif status == "done":
            stats["done_count"] += 1
            updated_at = str(row["updated_at"] or "")
            if updated_at and updated_at >= week_cutoff:
                stats["done_this_week"] += 1
        elif status == "ignored":
            stats["ignored_count"] += 1

        if normalized_query and not _item_matches_query(item, normalized_query):
            continue
        groups[status].append(item)

    limited_groups = {
        name: items[:limit_per_group]
        for name, items in groups.items()
    }
    return {"groups": limited_groups, "stats": stats}


def get_inbox_item(source: str, session_id: str) -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                q.*,
                m.created_at AS latest_created_at
            FROM session_queue q
            LEFT JOIN messages m ON m.id = q.latest_message_id
            WHERE q.source = ? AND q.session_id = ?
            """,
            (source, session_id),
        ).fetchone()

    if row is None:
        raise KeyError((source, session_id))
    return _row_to_item(row)


def ensure_queue_entry(source: str, session_id: str) -> dict[str, Any]:
    try:
        return get_inbox_item(source, session_id)
    except KeyError:
        session = _build_session_from_messages(source, session_id)
        payload = _session_to_payload(session)
        status = _default_status_for_priority(payload["ai_priority"])
        with get_conn() as conn:
            _upsert_queue_row(
                conn,
                source=source,
                session_id=session_id,
                payload=payload,
                existing=None,
                status=status,
            )
        return get_inbox_item(source, session_id)


def confirm_session_metadata(
    source: str,
    session_id: str,
    *,
    title: str | None = None,
    tags: list[str] | None = None,
    priority: str | None = None,
) -> dict[str, Any]:
    ensure_queue_entry(source, session_id)
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE session_queue
            SET
                user_title = ?,
                user_tags_json = ?,
                user_priority = ?,
                status = 'ready',
                last_reviewed_at = datetime('now'),
                updated_at = datetime('now')
            WHERE source = ? AND session_id = ?
            """,
            (
                title.strip() if title else None,
                json.dumps(tags or [], ensure_ascii=False),
                priority.strip() if priority else None,
                source,
                session_id,
            ),
        )
    return get_inbox_item(source, session_id)


def mark_session_ready(source: str, session_id: str) -> dict[str, Any]:
    ensure_queue_entry(source, session_id)
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE session_queue
            SET
                status = 'ready',
                snooze_until = NULL,
                last_reviewed_at = datetime('now'),
                updated_at = datetime('now')
            WHERE source = ? AND session_id = ?
            """,
            (source, session_id),
        )
    return get_inbox_item(source, session_id)


def mark_session_later(source: str, session_id: str, snooze_until: str | None = None) -> dict[str, Any]:
    ensure_queue_entry(source, session_id)
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE session_queue
            SET
                status = 'later',
                snooze_until = ?,
                last_reviewed_at = datetime('now'),
                updated_at = datetime('now')
            WHERE source = ? AND session_id = ?
            """,
            (snooze_until, source, session_id),
        )
    return get_inbox_item(source, session_id)


def mark_session_ignored(source: str, session_id: str) -> dict[str, Any]:
    ensure_queue_entry(source, session_id)
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE session_queue
            SET
                status = 'ignored',
                last_reviewed_at = datetime('now'),
                updated_at = datetime('now')
            WHERE source = ? AND session_id = ?
            """,
            (source, session_id),
        )
    return get_inbox_item(source, session_id)


def mark_session_done(source: str, session_id: str, note_id: int | None = None) -> dict[str, Any]:
    ensure_queue_entry(source, session_id)
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE session_queue
            SET
                status = 'done',
                note_id = COALESCE(?, note_id),
                snooze_until = NULL,
                last_reviewed_at = datetime('now'),
                updated_at = datetime('now')
            WHERE source = ? AND session_id = ?
            """,
            (note_id, source, session_id),
        )
    return get_inbox_item(source, session_id)


def mark_messages_done(messages: list[dict[str, Any]], note_id: int | None = None) -> dict[str, Any] | None:
    session_pairs = {
        (str(message.get("source")), str(message.get("session_id")))
        for message in messages
        if message.get("session_id")
    }
    if len(session_pairs) != 1:
        return None
    source, session_id = next(iter(session_pairs))
    return mark_session_done(source, session_id, note_id=note_id)


def reopen_sessions_for_deleted_note(note_id: int, session_pairs: list[dict[str, Any]]) -> None:
    if not session_pairs:
        return

    with get_conn() as conn:
        for pair in session_pairs:
            conn.execute(
                """
                UPDATE session_queue
                SET
                    status = 'ready',
                    note_id = NULL,
                    snooze_until = NULL,
                    updated_at = datetime('now')
                WHERE source = ? AND session_id = ?
                """,
                (pair["source"], pair["session_id"]),
            )
