from __future__ import annotations

import io
import json
import re
import zipfile
from typing import Any

from app.db import get_conn


NOTE_STATUS_LABELS = {
    "draft": "草稿",
    "reviewed": "已复核",
    "published": "已发布",
}

APPEND_SECTION_LABELS = {
    "problem": "问题描述",
    "root_cause": "根本原因",
    "solution": "解决方案",
    "key_takeaways": "关键收获",
}


NOTE_PROJECTION = """
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
    COALESCE(
        (SELECT COUNT(*) FROM note_sources ns WHERE ns.note_id = n.id),
        0
    ) AS source_count,
    COALESCE(
        (
            SELECT GROUP_CONCAT(DISTINCT m.source)
            FROM note_sources ns
            JOIN messages m ON m.id = ns.message_id
            WHERE ns.note_id = n.id
        ),
        ''
    ) AS source_labels,
    COALESCE(
        (
            SELECT GROUP_CONCAT(tag)
            FROM (
                SELECT nt.tag AS tag
                FROM note_tags nt
                WHERE nt.note_id = n.id
                ORDER BY nt.sort_order ASC, nt.tag ASC
            )
        ),
        ''
    ) AS note_tags_csv
"""


STACK_RULES: list[dict[str, Any]] = [
    {"tag": "FastAPI", "keywords": ("fastapi", "uvicorn", "pydantic", "starlette"), "min_hits": 1},
    {"tag": "Python", "keywords": ("python", "pytest", "asyncio", "pip", "venv", ".py"), "min_hits": 1},
    {"tag": "React", "keywords": ("react", "jsx", "usestate", "useeffect", "tsx"), "min_hits": 1},
    {"tag": "TypeScript", "keywords": ("typescript", "tsconfig", ".tsx", ".ts"), "min_hits": 1},
    {"tag": "Node.js", "keywords": ("node.js", "nodejs", "pnpm", "express", "next.js"), "min_hits": 1},
    {"tag": "JavaScript", "keywords": ("javascript", ".js", "commonjs", "yarn"), "min_hits": 1},
    {"tag": "C++", "keywords": ("c++", "std::", "#include", "public:", "private:", "nullptr", "vector<"), "min_hits": 1},
    {"tag": "Objective-C", "keywords": ("objective-c", "objc", "@selector", "@interface", "@implementation", "selector", "runtime"), "min_hits": 2},
    {"tag": "Swift", "keywords": ("swift", "swiftui", "uikit", ".swift", "optional("), "min_hits": 1},
    {"tag": "Go", "keywords": ("golang", "goroutine", "go mod", "go test", "go build", "channel"), "min_hits": 1},
    {"tag": "Rust", "keywords": ("rust", "cargo", "ownership", "borrow checker", "serde", "trait "), "min_hits": 1},
    {"tag": "Java", "keywords": ("spring", "maven", "gradle", "jvm", ".java"), "min_hits": 1},
    {"tag": "Kotlin", "keywords": ("kotlin", "jetpack compose", "coroutines", ".kt"), "min_hits": 1},
    {"tag": "SQLite", "keywords": ("sqlite", "sqlite3", "fts5"), "min_hits": 1},
    {"tag": "PostgreSQL", "keywords": ("postgres", "postgresql"), "min_hits": 1},
    {"tag": "Redis", "keywords": ("redis", "redis-cli", "cache aside"), "min_hits": 1},
    {"tag": "Docker", "keywords": ("docker", "dockerfile", "docker compose"), "min_hits": 1},
    {"tag": "Kubernetes", "keywords": ("kubernetes", "k8s", "kubectl"), "min_hits": 1},
]

SIMILARITY_STOP_TOKENS = {
    "这个",
    "那个",
    "以及",
    "然后",
    "因为",
    "所以",
    "如果",
    "已经",
    "还是",
    "需要",
    "建议",
    "问题",
    "方案",
    "原因",
    "解决",
    "补充",
    "当前",
    "内容",
    "笔记",
    "draft",
    "reviewed",
    "published",
}


def _split_csv(value: Any) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item and item.strip()]


def _parse_json_array(raw: Any) -> list[Any]:
    try:
        parsed = json.loads(str(raw or "[]"))
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _normalize_tags(tags: list[str] | None, limit: int = 12) -> list[str]:
    if not tags:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        cleaned = str(tag or "").strip()
        if not cleaned:
            continue
        lowered = cleaned.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(cleaned[:40])
        if len(normalized) >= limit:
            break
    return normalized


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _tokenize_for_similarity(value: str, max_tokens: int = 40) -> set[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return set()

    tokens: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"[a-z0-9_+.#-]{2,}|[\u4e00-\u9fff]{2,}", normalized):
        chunk = match.group(0)
        candidates: list[str]
        if re.fullmatch(r"[\u4e00-\u9fff]{2,}", chunk):
            candidates = [chunk]
            if len(chunk) > 3:
                candidates.extend(chunk[index : index + 2] for index in range(len(chunk) - 1))
            if len(chunk) > 4:
                candidates.extend(chunk[index : index + 3] for index in range(len(chunk) - 2))
        else:
            candidates = [chunk]

        for candidate in candidates:
            cleaned = candidate.strip()
            if len(cleaned) < 2 or cleaned in SIMILARITY_STOP_TOKENS or cleaned in seen:
                continue
            seen.add(cleaned)
            tokens.append(cleaned)
            if len(tokens) >= max_tokens:
                return set(tokens)
    return set(tokens)


def _similarity_reason(note: dict[str, Any], shared_tags: list[str], shared_terms: list[str]) -> str:
    if shared_tags:
        return f"共享标签：{' / '.join(shared_tags[:3])}"
    if shared_terms:
        return f"内容接近：{' / '.join(shared_terms[:3])}"
    return "可能是同一主题的后续补充"


def _load_note_tags(conn: Any, note_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT tag
        FROM note_tags
        WHERE note_id = ?
        ORDER BY sort_order ASC, tag ASC
        """,
        (note_id,),
    ).fetchall()
    return [str(row["tag"]).strip() for row in rows if str(row["tag"]).strip()]


def _replace_note_tags(conn: Any, note_id: int, tags: list[str] | None) -> None:
    normalized_tags = _normalize_tags(tags)
    conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
    if not normalized_tags:
        return

    conn.executemany(
        """
        INSERT INTO note_tags(note_id, tag, sort_order)
        VALUES (?, ?, ?)
        """,
        [(note_id, tag, index) for index, tag in enumerate(normalized_tags)],
    )


def _append_unique_text(existing: str, incoming: str) -> str:
    existing_text = str(existing or "").strip()
    incoming_text = str(incoming or "").strip()
    if not incoming_text:
        return existing_text
    if not existing_text:
        return incoming_text

    normalized_existing = " ".join(existing_text.split())
    normalized_incoming = " ".join(incoming_text.split())
    if not normalized_incoming or normalized_incoming in normalized_existing:
        return existing_text
    return f"{existing_text.rstrip()}\n\n{incoming_text}"


def _remove_appended_text(current: str, incoming: str) -> str:
    current_text = str(current or "")
    incoming_text = str(incoming or "").strip()
    if not incoming_text:
        return current_text

    trimmed_current = current_text.rstrip()
    if trimmed_current == incoming_text:
        return ""

    separator = f"\n\n{incoming_text}"
    if trimmed_current.endswith(separator):
        return trimmed_current[: -len(separator)].rstrip()
    if trimmed_current.endswith(incoming_text):
        return trimmed_current[: -len(incoming_text)].rstrip()
    return current_text


def _has_append_change(existing: str, incoming: str) -> bool:
    existing_text = str(existing or "").strip()
    incoming_text = str(incoming or "").strip()
    if not incoming_text:
        return False
    if not existing_text:
        return True

    normalized_existing = " ".join(existing_text.split()).lower()
    normalized_incoming = " ".join(incoming_text.split()).lower()
    return bool(normalized_incoming) and normalized_incoming not in normalized_existing


def _merge_source_type(existing_type: str, incoming_type: str) -> str:
    current = str(existing_type or "").strip()
    incoming = str(incoming_type or "").strip()
    if not current:
        return incoming or "mixed"
    if not incoming or current == incoming:
        return current
    return "mixed"


def _append_note_sources(conn: Any, note_id: int, message_ids: list[int]) -> list[int]:
    pending_ids = _pending_note_source_ids(conn, note_id, message_ids)
    if not pending_ids:
        return []

    max_order_row = conn.execute(
        """
        SELECT COALESCE(MAX(sort_order), -1) AS max_sort_order
        FROM note_sources
        WHERE note_id = ?
        """,
        (note_id,),
    ).fetchone()
    start_index = int(max_order_row["max_sort_order"] or -1) + 1
    conn.executemany(
        """
        INSERT INTO note_sources(note_id, message_id, sort_order)
        VALUES (?, ?, ?)
        """,
        [
            (note_id, message_id, start_index + offset)
            for offset, message_id in enumerate(pending_ids)
        ],
    )
    return pending_ids


def _pending_note_source_ids(conn: Any, note_id: int, message_ids: list[int]) -> list[int]:
    existing_rows = conn.execute(
        """
        SELECT message_id
        FROM note_sources
        WHERE note_id = ?
        """,
        (note_id,),
    ).fetchall()
    existing_ids = {int(row["message_id"]) for row in existing_rows}
    return [message_id for message_id in dict.fromkeys(message_ids) if message_id not in existing_ids]


def _build_append_summary(
    *,
    current: dict[str, Any],
    incoming: dict[str, str],
    existing_tags: list[str],
    merged_tags: list[str],
    added_source_count: int,
) -> dict[str, Any]:
    changed_sections: list[str] = []
    unchanged_sections: list[str] = []
    section_updates: list[dict[str, str]] = []
    for field, label in APPEND_SECTION_LABELS.items():
        if _has_append_change(str(current.get(field) or ""), str(incoming.get(field) or "")):
            changed_sections.append(label)
            section_updates.append(
                {
                    "field": field,
                    "label": label,
                    "incoming_text": str(incoming.get(field) or "").strip(),
                }
            )
        else:
            unchanged_sections.append(label)

    existing_tag_set = {tag.casefold() for tag in existing_tags}
    added_tags = [tag for tag in merged_tags if tag.casefold() not in existing_tag_set]

    summary_parts: list[str] = []
    if added_source_count > 0:
        summary_parts.append(f"新增 {added_source_count} 条来源")
    if changed_sections:
        summary_parts.append(f"补充了 {'、'.join(changed_sections)}")
    if added_tags:
        summary_parts.append(f"带入标签：{' / '.join(added_tags)}")
    if not summary_parts:
        summary_parts.append("这次追加没有带来新的结构化变化")

    can_append = bool(added_source_count > 0 or changed_sections)
    blocking_reason = "" if can_append else "没有检测到新的来源或新增段落，这次追加已拦截。"

    return {
        "source_count_added": added_source_count,
        "changed_sections": changed_sections,
        "unchanged_sections": unchanged_sections,
        "section_updates": section_updates,
        "added_tags": added_tags,
        "summary_text": "；".join(summary_parts),
        "can_append": can_append,
        "blocking_reason": blocking_reason,
    }


def _clip_text(value: str, max_len: int = 120) -> str:
    text = str(value or "").strip()
    return text[:max_len] + ("..." if len(text) > max_len else "")


def _infer_append_origin(messages: list[dict[str, Any]]) -> dict[str, str | None]:
    session_pairs = {
        (str(message.get("source") or "").strip(), str(message.get("session_id") or "").strip())
        for message in messages
        if str(message.get("source") or "").strip()
    }
    normalized_pairs = {(source, session_id) for source, session_id in session_pairs if source}
    if len(normalized_pairs) == 1:
        source, session_id = next(iter(normalized_pairs))
        if session_id:
            return {
                "source": source,
                "session_id": session_id,
                "origin_label": f"{source} / {session_id}",
            }
        return {
            "source": source,
            "session_id": None,
            "origin_label": f"{source} / 手动补充消息",
        }

    sources = sorted({source for source, _ in normalized_pairs if source})
    if len(sources) == 1:
        return {
            "source": sources[0],
            "session_id": None,
            "origin_label": f"{sources[0]} / 手动筛选补充",
        }

    first_snippet = next(
        (_clip_text(str(message.get("content") or ""), 36) for message in messages if str(message.get("content") or "").strip()),
        "",
    )
    return {
        "source": None,
        "session_id": None,
        "origin_label": first_snippet or "混合来源补充",
    }


def _record_append_event(
    conn: Any,
    *,
    note_id: int,
    messages: list[dict[str, Any]],
    summary: dict[str, Any],
    added_message_ids: list[int],
    previous_tags: list[str],
    previous_status: str,
    previous_source_type: str,
) -> None:
    origin = _infer_append_origin(messages)
    conn.execute(
        """
        INSERT INTO note_append_events(
            note_id,
            source,
            session_id,
            origin_label,
            source_count_added,
            summary_text,
            changed_sections_json,
            added_tags_json,
            section_updates_json
            ,
            added_message_ids_json,
            previous_tags_json,
            previous_status,
            previous_source_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            note_id,
            origin.get("source"),
            origin.get("session_id"),
            origin.get("origin_label") or "追加补充",
            int(summary.get("source_count_added") or 0),
            str(summary.get("summary_text") or ""),
            json.dumps(summary.get("changed_sections") or [], ensure_ascii=False),
            json.dumps(summary.get("added_tags") or [], ensure_ascii=False),
            json.dumps(summary.get("section_updates") or [], ensure_ascii=False),
            json.dumps(added_message_ids or [], ensure_ascii=False),
            json.dumps(previous_tags or [], ensure_ascii=False),
            str(previous_status or "draft"),
            str(previous_source_type or "manual"),
        ),
    )


def _detect_stack_tags(note: dict[str, Any], limit: int = 2) -> list[str]:
    text = " ".join(
        str(note.get(field) or "")
        for field in ("title", "problem", "root_cause", "solution", "key_takeaways")
    ).lower()
    if not text.strip():
        return []

    matched: list[tuple[int, int, str]] = []
    for index, rule in enumerate(STACK_RULES):
        score = sum(1 for keyword in rule["keywords"] if keyword.lower() in text)
        if score >= int(rule["min_hits"]):
            matched.append((score, -index, str(rule["tag"])))

    matched.sort(reverse=True)
    return [tag for _, _, tag in matched[:limit]]


def _normalize_note_row(row: Any) -> dict[str, Any]:
    note = dict(row)
    note["source_labels"] = _split_csv(note.get("source_labels"))
    note["source_count"] = int(note.get("source_count") or 0)
    note["status_label"] = NOTE_STATUS_LABELS.get(str(note.get("status") or ""), str(note.get("status") or ""))
    note["tags"] = _split_csv(note.get("note_tags_csv"))
    note["stack_tags"] = _detect_stack_tags(note)
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
    tags: list[str] | None = None,
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
            [(note_id, message_id, index) for index, message_id in enumerate(dict.fromkeys(message_ids))],
        )
        _replace_note_tags(conn, note_id, tags)

    return get_note(note_id)


def append_to_note(
    note_id: int,
    *,
    problem: str,
    root_cause: str,
    solution: str,
    key_takeaways: str,
    message_ids: list[int],
    messages: list[dict[str, Any]] | None = None,
    source_type: str = "mixed",
    tags: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, title, problem, root_cause, solution, key_takeaways, status, source_type, updated_at
            FROM notes
            WHERE id = ?
            """,
            (note_id,),
        ).fetchone()
        if row is None:
            raise KeyError(note_id)

        current = dict(row)
        existing_tags = _load_note_tags(conn, note_id)
        merged_tags = _normalize_tags([*existing_tags, *(_normalize_tags(tags) or [])])
        pending_message_ids = _pending_note_source_ids(conn, note_id, message_ids)
        summary = _build_append_summary(
            current=current,
            incoming={
                "problem": problem,
                "root_cause": root_cause,
                "solution": solution,
                "key_takeaways": key_takeaways,
            },
            existing_tags=existing_tags,
            merged_tags=merged_tags,
            added_source_count=len(pending_message_ids),
        )
        if not summary["can_append"]:
            raise ValueError(summary["blocking_reason"])
        conn.execute(
            """
            UPDATE notes
            SET
                problem = ?,
                root_cause = ?,
                solution = ?,
                key_takeaways = ?,
                status = 'draft',
                source_type = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                _append_unique_text(str(current.get("problem") or ""), problem),
                _append_unique_text(str(current.get("root_cause") or ""), root_cause),
                _append_unique_text(str(current.get("solution") or ""), solution),
                _append_unique_text(str(current.get("key_takeaways") or ""), key_takeaways),
                _merge_source_type(str(current.get("source_type") or ""), source_type),
                note_id,
            ),
        )
        added_message_ids = _append_note_sources(conn, note_id, pending_message_ids)
        _replace_note_tags(conn, note_id, merged_tags)
        if messages:
            _record_append_event(
                conn,
                note_id=note_id,
                messages=messages,
                summary=summary,
                added_message_ids=added_message_ids,
                previous_tags=existing_tags,
                previous_status=str(current.get("status") or "draft"),
                previous_source_type=str(current.get("source_type") or "manual"),
            )

    return get_note(note_id), summary


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
    tags: list[str] | None = None,
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
        _replace_note_tags(conn, note_id, tags)

    if cur.rowcount == 0:
        raise KeyError(note_id)

    return get_note(note_id)


def delete_note(note_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        source_rows = conn.execute(
            """
            SELECT DISTINCT m.source, m.session_id
            FROM note_sources ns
            JOIN messages m ON m.id = ns.message_id
            WHERE ns.note_id = ?
              AND COALESCE(m.session_id, '') <> ''
            """,
            (note_id,),
        ).fetchall()
        cur = conn.execute(
            """
            DELETE FROM notes
            WHERE id = ?
            """,
            (note_id,),
        )

    if cur.rowcount == 0:
        raise KeyError(note_id)

    return [dict(row) for row in source_rows]


def get_note(note_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            f"""
            SELECT {NOTE_PROJECTION}
            FROM notes n
            WHERE n.id = ?
            """,
            (note_id,),
        ).fetchone()

    if row is None:
        raise KeyError(note_id)

    return _normalize_note_row(row)


def latest_notes(
    limit: int = 30,
    *,
    status: str | None = None,
    exclude_status: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        clauses.append("n.status = ?")
        args.append(status)
    if exclude_status:
        clauses.append("n.status <> ?")
        args.append(exclude_status)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT {NOTE_PROJECTION}
            FROM notes n
            {where_sql}
            ORDER BY n.updated_at DESC, n.id DESC
            LIMIT ?
            """,
            tuple([*args, limit]),
        ).fetchall()

    return [_normalize_note_row(row) for row in rows]


def latest_note_options(limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                n.id,
                n.title,
                n.status,
                n.updated_at,
                COALESCE(
                    (SELECT COUNT(*) FROM note_sources ns WHERE ns.note_id = n.id),
                    0
                ) AS source_count,
                COALESCE(
                    (
                        SELECT GROUP_CONCAT(tag)
                        FROM (
                            SELECT nt.tag AS tag
                            FROM note_tags nt
                            WHERE nt.note_id = n.id
                            ORDER BY nt.sort_order ASC, nt.tag ASC
                        )
                    ),
                    ''
                ) AS note_tags_csv
            FROM notes n
            ORDER BY n.updated_at DESC, n.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    options: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        options.append(
            {
                "id": int(item["id"]),
                "title": str(item.get("title") or ""),
                "status": str(item.get("status") or "draft"),
                "status_label": NOTE_STATUS_LABELS.get(str(item.get("status") or ""), str(item.get("status") or "")),
                "updated_at": str(item.get("updated_at") or ""),
                "source_count": int(item.get("source_count") or 0),
                "tags": _split_csv(item.get("note_tags_csv")),
            }
        )
    return options


def recommend_notes(
    *,
    title: str,
    problem: str,
    root_cause: str,
    solution: str,
    key_takeaways: str,
    tags: list[str] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    candidates = latest_notes(limit=200)
    query_tags = _normalize_tags(tags)
    title_text = str(title or "").strip()
    query_text = "\n".join(
        part
        for part in (
            title_text,
            problem,
            root_cause,
            solution,
            key_takeaways,
            " ".join(query_tags),
        )
        if str(part or "").strip()
    )
    if not query_text.strip():
        return []

    query_tokens = _tokenize_for_similarity(query_text)
    title_tokens = _tokenize_for_similarity(title_text, max_tokens=16)
    ranked: list[tuple[int, str, dict[str, Any]]] = []

    for note in candidates:
        note_tags = _normalize_tags(list(note.get("tags") or []))
        note_text = "\n".join(
            str(note.get(field) or "")
            for field in ("title", "problem", "root_cause", "solution", "key_takeaways")
        )
        note_tokens = _tokenize_for_similarity(note_text, max_tokens=80)
        shared_tags = [tag for tag in query_tags if tag in note_tags]
        shared_terms = [term for term in query_tokens if term in note_tokens]
        shared_title_terms = [term for term in title_tokens if term in note_tokens]

        score = len(shared_tags) * 10
        score += min(len(shared_title_terms), 4) * 4
        score += min(len(shared_terms), 10)

        note_title = str(note.get("title") or "").strip().lower()
        if title_text and note_title:
            lowered_title = title_text.lower()
            if lowered_title == note_title:
                score += 12
            elif lowered_title in note_title or note_title in lowered_title:
                score += 6

        if score <= 0:
            continue

        item = {
            "id": int(note["id"]),
            "title": str(note.get("title") or ""),
            "status": str(note.get("status") or "draft"),
            "status_label": str(note.get("status_label") or NOTE_STATUS_LABELS.get(str(note.get("status") or ""), "")),
            "updated_at": str(note.get("updated_at") or ""),
            "source_count": int(note.get("source_count") or 0),
            "tags": note_tags,
            "match_reason": _similarity_reason(note, shared_tags, shared_terms or shared_title_terms),
        }
        ranked.append((score, item["updated_at"], item))

    ranked.sort(key=lambda item: (item[0], item[1], item[2]["id"]), reverse=True)
    return [item for _, _, item in ranked[:limit]]


def search_notes(query: str, limit: int = 20) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            WITH matched AS (
                SELECT rowid AS note_id, bm25(notes_fts) AS rank
                FROM notes_fts
                WHERE notes_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            )
            SELECT {NOTE_PROJECTION}
            FROM matched
            JOIN notes n ON n.id = matched.note_id
            ORDER BY matched.rank, n.id DESC
            """,
            (query, limit),
        ).fetchall()

        if not rows:
            tokens = [t for t in query.replace("OR", " ").split() if t]
            if tokens:
                where_clause = " OR ".join(
                    [
                        "n.title LIKE ?",
                        "n.problem LIKE ?",
                        "n.root_cause LIKE ?",
                        "n.solution LIKE ?",
                        "n.key_takeaways LIKE ?",
                        "EXISTS (SELECT 1 FROM note_tags nt WHERE nt.note_id = n.id AND nt.tag LIKE ?)",
                    ]
                    * len(tokens)
                )
                args: list[Any] = []
                for token in tokens:
                    like = f"%{token}%"
                    args.extend([like, like, like, like, like, like])
                args.append(limit)
                rows = conn.execute(
                    f"""
                    SELECT {NOTE_PROJECTION}
                    FROM notes n
                    WHERE {where_clause}
                    ORDER BY n.updated_at DESC, n.id DESC
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


def _sanitize_export_filename(title: str, fallback: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", str(title or "").strip(), flags=re.UNICODE).strip("-")
    return (cleaned or fallback)[:80]


def export_note_markdown(note_id: int) -> tuple[str, str]:
    note = get_note(note_id)
    sources = get_note_sources(note_id)

    lines: list[str] = [f"# {note['title']}", ""]
    lines.extend(
        [
            f"- 状态: {note.get('status_label') or note.get('status') or '未标记'}",
            f"- 来源类型: {note.get('source_type') or 'mixed'}",
            f"- 来源数量: {note.get('source_count') or 0}",
            f"- 创建时间: {note.get('created_at') or ''}",
            f"- 更新时间: {note.get('updated_at') or ''}",
        ]
    )
    if note.get("tags"):
        lines.append(f"- 标签: {', '.join(str(tag) for tag in note['tags'])}")
    if note.get("source_labels"):
        lines.append(f"- 来源平台: {', '.join(str(label) for label in note['source_labels'])}")

    sections = [
        ("问题描述", str(note.get("problem") or "").strip()),
        ("根本原因", str(note.get("root_cause") or "").strip()),
        ("解决方案", str(note.get("solution") or "").strip()),
        ("关键收获", str(note.get("key_takeaways") or "").strip()),
    ]
    for label, body in sections:
        lines.extend(["", f"## {label}", "", body or "（空）"])

    lines.extend(["", "## 来源对话", ""])
    if not sources:
        lines.append("暂无来源消息。")
    else:
        for index, item in enumerate(sources, start=1):
            lines.extend(
                [
                    f"### 来源 {index}",
                    "",
                    f"- 平台: {item.get('source') or ''}",
                    f"- 会话: {item.get('session_id') or '无'}",
                    f"- 角色: {item.get('role') or ''}",
                    f"- 时间: {item.get('created_at') or ''}",
                    "",
                    "```text",
                    str(item.get("content") or "").strip(),
                    "```",
                    "",
                ]
            )

    markdown = "\n".join(lines).strip() + "\n"
    filename = f"{_sanitize_export_filename(str(note.get('title') or ''), f'note-{note_id}')}.md"
    return markdown, filename


def export_notes_markdown_zip(note_ids: list[int]) -> tuple[bytes, str]:
    unique_note_ids = list(dict.fromkeys(int(note_id) for note_id in note_ids))
    if not unique_note_ids:
        raise KeyError("note ids required")

    buffer = io.BytesIO()
    used_names: dict[str, int] = {}
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for note_id in unique_note_ids:
            markdown, filename = export_note_markdown(note_id)
            stem = filename[:-3] if filename.endswith(".md") else filename
            counter = used_names.get(filename, 0)
            used_names[filename] = counter + 1
            final_name = filename if counter == 0 else f"{stem}-{counter + 1}.md"
            archive.writestr(final_name, markdown)

    return buffer.getvalue(), "notes-export.zip"


def _can_undo_append_event(note_updated_at: str, latest_event_id: int, row: dict[str, Any]) -> bool:
    return bool(
        latest_event_id
        and int(row.get("id") or 0) == int(latest_event_id)
        and str(note_updated_at or "") == str(row.get("created_at") or "")
    )


def list_note_append_events(note_id: int, limit: int = 30) -> list[dict[str, Any]]:
    with get_conn() as conn:
        note_row = conn.execute(
            """
            SELECT updated_at
            FROM notes
            WHERE id = ?
            """,
            (note_id,),
        ).fetchone()
        latest_event_row = conn.execute(
            """
            SELECT id
            FROM note_append_events
            WHERE note_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (note_id,),
        ).fetchone()
        rows = conn.execute(
            """
            SELECT
                id,
                note_id,
                source,
                session_id,
                origin_label,
                source_count_added,
                summary_text,
                changed_sections_json,
                added_tags_json,
                section_updates_json,
                added_message_ids_json,
                previous_tags_json,
                previous_status,
                previous_source_type,
                created_at
            FROM note_append_events
            WHERE note_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (note_id, limit),
        ).fetchall()

    note_updated_at = str(note_row["updated_at"] or "") if note_row is not None else ""
    latest_event_id = int(latest_event_row["id"] or 0) if latest_event_row is not None else 0
    events: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        changed_sections = _parse_json_array(item.get("changed_sections_json"))
        added_tags = _parse_json_array(item.get("added_tags_json"))
        section_updates = _parse_json_array(item.get("section_updates_json"))
        added_message_ids = [int(value) for value in _parse_json_array(item.get("added_message_ids_json")) if str(value).strip()]
        previous_tags = [str(value) for value in _parse_json_array(item.get("previous_tags_json")) if str(value).strip()]

        events.append(
            {
                "id": int(item["id"]),
                "note_id": int(item["note_id"]),
                "source": str(item.get("source") or ""),
                "session_id": str(item.get("session_id") or ""),
                "origin_label": str(item.get("origin_label") or "追加补充"),
                "source_count_added": int(item.get("source_count_added") or 0),
                "summary_text": str(item.get("summary_text") or ""),
                "changed_sections": [str(value) for value in changed_sections if str(value).strip()],
                "added_tags": [str(value) for value in added_tags if str(value).strip()],
                "section_updates": [
                    {
                        "field": str(update.get("field") or ""),
                        "label": str(update.get("label") or ""),
                        "incoming_text": str(update.get("incoming_text") or ""),
                    }
                    for update in section_updates
                    if isinstance(update, dict)
                ],
                "added_message_ids": added_message_ids,
                "previous_tags": previous_tags,
                "previous_status": str(item.get("previous_status") or "draft"),
                "previous_source_type": str(item.get("previous_source_type") or "manual"),
                "created_at": str(item.get("created_at") or ""),
                "can_undo": _can_undo_append_event(note_updated_at, latest_event_id, item),
            }
        )
    return events


def undo_note_append(note_id: int, event_id: int) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    with get_conn() as conn:
        note_row = conn.execute(
            """
            SELECT id, problem, root_cause, solution, key_takeaways, status, source_type, updated_at
            FROM notes
            WHERE id = ?
            """,
            (note_id,),
        ).fetchone()
        if note_row is None:
            raise KeyError(note_id)

        event_row = conn.execute(
            """
            SELECT
                id,
                note_id,
                source,
                session_id,
                origin_label,
                source_count_added,
                summary_text,
                changed_sections_json,
                added_tags_json,
                section_updates_json,
                added_message_ids_json,
                previous_tags_json,
                previous_status,
                previous_source_type,
                created_at
            FROM note_append_events
            WHERE note_id = ? AND id = ?
            """,
            (note_id, event_id),
        ).fetchone()
        if event_row is None:
            raise KeyError(event_id)

        latest_event_row = conn.execute(
            """
            SELECT id
            FROM note_append_events
            WHERE note_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (note_id,),
        ).fetchone()
        latest_event_id = int(latest_event_row["id"] or 0) if latest_event_row is not None else 0
        event = dict(event_row)
        if not _can_undo_append_event(str(note_row["updated_at"] or ""), latest_event_id, event):
            raise ValueError("append event can no longer be undone")

        section_updates = [
            update
            for update in _parse_json_array(event.get("section_updates_json"))
            if isinstance(update, dict)
        ]
        added_message_ids = [int(value) for value in _parse_json_array(event.get("added_message_ids_json")) if str(value).strip()]
        previous_tags = [str(value) for value in _parse_json_array(event.get("previous_tags_json")) if str(value).strip()]

        reverted_fields = {
            "problem": str(note_row["problem"] or ""),
            "root_cause": str(note_row["root_cause"] or ""),
            "solution": str(note_row["solution"] or ""),
            "key_takeaways": str(note_row["key_takeaways"] or ""),
        }
        for update in section_updates:
            field = str(update.get("field") or "")
            if field not in reverted_fields:
                continue
            reverted_fields[field] = _remove_appended_text(reverted_fields[field], str(update.get("incoming_text") or ""))

        conn.execute(
            """
            UPDATE notes
            SET
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
                reverted_fields["problem"],
                reverted_fields["root_cause"],
                reverted_fields["solution"],
                reverted_fields["key_takeaways"],
                str(event.get("previous_status") or "draft"),
                str(event.get("previous_source_type") or "manual"),
                note_id,
            ),
        )
        if added_message_ids:
            placeholders = ",".join("?" for _ in added_message_ids)
            conn.execute(
                f"""
                DELETE FROM note_sources
                WHERE note_id = ?
                  AND message_id IN ({placeholders})
                """,
                tuple([note_id, *added_message_ids]),
            )
        _replace_note_tags(conn, note_id, previous_tags)
        conn.execute(
            """
            DELETE FROM note_append_events
            WHERE id = ?
            """,
            (event_id,),
        )

        reopen_pairs: list[dict[str, Any]] = []
        source = str(event.get("source") or "").strip()
        session_id = str(event.get("session_id") or "").strip()
        if source and session_id:
            remaining = conn.execute(
                """
                SELECT 1
                FROM note_sources ns
                JOIN messages m ON m.id = ns.message_id
                WHERE ns.note_id = ?
                  AND m.source = ?
                  AND m.session_id = ?
                LIMIT 1
                """,
                (note_id, source, session_id),
            ).fetchone()
            if remaining is None:
                reopen_pairs.append({"source": source, "session_id": session_id})

    note = get_note(note_id)
    events = list_note_append_events(note_id)
    return note, event, reopen_pairs if reopen_pairs else []
