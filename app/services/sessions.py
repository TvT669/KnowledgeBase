from __future__ import annotations

import json
import re
from typing import Any

from app.db import get_conn


TOPIC_RULES: list[dict[str, Any]] = [
    {
        "title": "重试与幂等设计",
        "keywords": ("幂等", "重试", "retry", "补偿", "重复写入"),
        "min_hits": 2,
    },
    {
        "title": "C++ public 声明位置错误",
        "keywords": ("public:", "access specifier", "invalid in c++", "placed outside of a class"),
        "min_hits": 1,
    },
    {
        "title": "字典（Dictionary）概念解释",
        "keywords": ("dictionary", "字典", "key-value", "键值"),
        "min_hits": 2,
    },
    {
        "title": "时间复杂度优化讨论",
        "keywords": ("时间复杂度", "复杂度", "o(n", "o(n^2)", "性能优化"),
        "min_hits": 2,
    },
    {
        "title": "线程安全与并发设计",
        "keywords": ("线程安全", "并发", "thread", "race condition"),
        "min_hits": 2,
    },
]

TAG_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("C++", ("c++", "public:", "std::", "#include", "nullptr")),
    ("Python", ("python", "pytest", "def ", "dict(", "list[")),
    ("FastAPI", ("fastapi", "uvicorn", "pydantic", "starlette")),
    ("Objective-C", ("objc", "selector", "runtime", "modf", "objective-c")),
    ("幂等", ("幂等", "retry", "重试")),
    ("补偿", ("补偿", "失败日志", "重复写入")),
    ("性能", ("复杂度", "o(n", "性能")),
    ("并发", ("线程安全", "并发", "thread")),
    ("概念解释", ("是什么", "简单说", "key-value", "dictionary", "解释")),
]

PROBLEM_SIGNALS = ("报错", "问题", "失败", "异常", "invalid", "issue", "error", "warning", "bug")
SOLUTION_SIGNALS = ("建议", "方案", "修复", "解决", "fix", "should", "可以", "需要", "避免", "补偿")
DECISION_SIGNALS = ("结论", "根因", "原因", "最佳", "推荐", "应该")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _clip(value: str, max_len: int = 46) -> str:
    text = _normalize_text(value)
    return text[:max_len] + ("..." if len(text) > max_len else "")


def _strip_command_prefix(value: str) -> str:
    text = value.strip()
    text = re.sub(r"^@\w+\s+", "", text)
    text = re.sub(r"^/\w+\s*", "", text)
    return text


def _first_sentence(value: str) -> str:
    text = _strip_command_prefix(value)
    text = re.sub(r"`+", "", text)
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"^#+\s*", "", text)
    text = text.splitlines()[0].strip() if text.splitlines() else text
    parts = re.split(r"[。！？!?]\s*", text)
    first = next((part.strip(" -:：") for part in parts if part.strip()), "")
    if first.lower().startswith("the issue is that "):
        first = first[18:]
    return _normalize_text(first)


def _is_bad_title_candidate(value: str) -> bool:
    text = value.strip()
    if len(text) < 6:
        return True
    if len(re.findall(r"[\\/]", text)) >= 3:
        return True
    if text.lower().startswith(("thread ", "queue :", "command swiftcompile failed")):
        return True
    if text.count("-") >= 4 and len(text) > 24:
        return True
    if text.lower().startswith(("http://", "https://", "/users/", "/bee/")):
        return True
    return False


def _recent_segment(messages: list[dict[str, Any]], max_messages: int = 8) -> list[dict[str, Any]]:
    if len(messages) <= max_messages:
        return messages

    user_indices = [index for index, message in enumerate(messages) if message.get("role") == "user"]
    if len(user_indices) >= 2:
        start = user_indices[-2]
        segment = messages[start:]
        return segment[-max_messages:]

    return messages[-max_messages:]


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    lower = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in lower)


def _match_topic_title(text: str) -> str | None:
    for rule in TOPIC_RULES:
        if _keyword_hits(text, rule["keywords"]) >= rule["min_hits"]:
            return rule["title"]
    return None


def _extract_tags(text: str) -> list[str]:
    lower = text.lower()
    tags: list[str] = []
    for tag, keywords in TAG_RULES:
        if any(keyword.lower() in lower for keyword in keywords):
            tags.append(tag)
        if len(tags) >= 3:
            break
    return tags


def _length_label(message_count: int) -> str:
    if message_count <= 3:
        return "短会话"
    if message_count <= 20:
        return "中等会话"
    return "长会话"


def _infer_session_title(messages: list[dict[str, Any]], latest_summary: str) -> str:
    combined = " ".join(message.get("content") or "" for message in messages)
    matched = _match_topic_title(combined)
    if matched:
        return matched

    for role in ("user", "assistant", "system"):
        for message in messages:
            if message.get("role") != role:
                continue
            sentence = _first_sentence(message.get("content") or "")
            if not _is_bad_title_candidate(sentence):
                return _clip(sentence, 34)

    fallback = _first_sentence(latest_summary)
    if _is_bad_title_candidate(fallback):
        lower = combined.lower()
        if any(keyword in lower for keyword in ("objc", "runtime", "selector", "modf")):
            return "Objective-C Runtime 编译问题"
        if any(keyword in lower for keyword in ("fastapi", "uvicorn", "pydantic")):
            return "后端接口实现讨论"
        if any(keyword in lower for keyword in ("复杂度", "o(n", "性能")):
            return "性能与复杂度讨论"
        if any(keyword in lower for keyword in ("c++", "public:", "std::")):
            return "C++ 代码讨论"
        return "待整理会话"
    return _clip(fallback or "未命名会话", 34)


def _infer_session_excerpt(messages: list[dict[str, Any]], latest_summary: str) -> str:
    candidates = [
        _normalize_text(latest_summary),
        *(_normalize_text(message.get("summary") or "") for message in reversed(messages)),
        *(_normalize_text(message.get("content") or "") for message in reversed(messages)),
    ]
    for candidate in candidates:
        if candidate:
            return _clip(candidate, 150)
    return "暂无摘要"


def _score_session(messages: list[dict[str, Any]], tags: list[str], title: str) -> tuple[int, str, str]:
    combined = " ".join(message.get("content") or "" for message in messages)
    message_count = len(messages)
    assistant_count = sum(1 for message in messages if message.get("role") == "assistant")
    user_count = sum(1 for message in messages if message.get("role") == "user")

    score = 0
    reasons: list[str] = []

    has_problem = any(signal in combined.lower() for signal in PROBLEM_SIGNALS)
    has_solution = any(signal in combined.lower() for signal in SOLUTION_SIGNALS)
    has_decision = any(signal in combined.lower() for signal in DECISION_SIGNALS)

    if 3 <= message_count <= 16:
        score += 1
        reasons.append("讨论长度适中")
    elif message_count > 25:
        reasons.append("包含较完整上下文")

    if assistant_count and user_count:
        score += 1
        reasons.append("包含问答往返")

    if has_problem and has_solution:
        score += 2
        reasons.insert(0, "同时出现问题与方案")
    elif has_problem or has_solution:
        score += 1

    if has_decision:
        score += 1
        reasons.insert(0, "包含明确结论")

    if tags:
        score += 1

    if "未命名会话" not in title and len(title) >= 6:
        score += 1

    if has_problem and has_solution and score >= 5:
        return score, "推荐优先整理", reasons[0] if reasons else "内容价值较高"
    if score >= 3:
        return score, "值得整理", reasons[0] if reasons else "已有清晰讨论线索"
    return score, "可稍后整理", reasons[0] if reasons else "更像零散片段"


def _build_session_insight(
    *,
    session: dict[str, Any],
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    segment = _recent_segment(messages)
    segment_text = " ".join(message.get("content") or "" for message in segment)
    title = _infer_session_title(segment, session.get("latest_summary") or "")
    excerpt = _infer_session_excerpt(segment, session.get("latest_summary") or "")
    tags = _extract_tags(f"{title} {excerpt} {segment_text}")
    score, label, reason = _score_session(segment, tags, title)

    return {
        "topic_title": title,
        "topic_excerpt": excerpt,
        "tags": tags,
        "length_label": _length_label(int(session["message_count"])),
        "priority_score": score,
        "priority_label": label,
        "priority_reason": reason,
        "latest_message_id": int(session["latest_id"]),
        "message_count": int(session["message_count"]),
    }


def _load_cached_insights(conn: Any, sessions: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    if not sessions:
        return {}

    clauses = []
    args: list[Any] = []
    for session in sessions:
        clauses.append("(source = ? AND session_id = ?)")
        args.extend([session["source"], session["session_id"]])

    rows = conn.execute(
        f"""
        SELECT
            source,
            session_id,
            latest_message_id,
            message_count,
            topic_title,
            topic_excerpt,
            tags_json,
            length_label,
            priority_score,
            priority_label,
            priority_reason,
            updated_at
        FROM session_insights
        WHERE {" OR ".join(clauses)}
        """,
        tuple(args),
    ).fetchall()

    insights: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        data = dict(row)
        try:
            tags = json.loads(data.get("tags_json") or "[]")
        except json.JSONDecodeError:
            tags = []
        data["tags"] = tags if isinstance(tags, list) else []
        insights[(data["source"], data["session_id"])] = data
    return insights


def _cache_session_insight(conn: Any, session: dict[str, Any], insight: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO session_insights(
            source,
            session_id,
            latest_message_id,
            message_count,
            topic_title,
            topic_excerpt,
            tags_json,
            length_label,
            priority_score,
            priority_label,
            priority_reason,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(source, session_id) DO UPDATE SET
            latest_message_id = excluded.latest_message_id,
            message_count = excluded.message_count,
            topic_title = excluded.topic_title,
            topic_excerpt = excluded.topic_excerpt,
            tags_json = excluded.tags_json,
            length_label = excluded.length_label,
            priority_score = excluded.priority_score,
            priority_label = excluded.priority_label,
            priority_reason = excluded.priority_reason,
            updated_at = datetime('now')
        """,
        (
            session["source"],
            session["session_id"],
            insight["latest_message_id"],
            insight["message_count"],
            insight["topic_title"],
            insight["topic_excerpt"],
            json.dumps(insight["tags"], ensure_ascii=False),
            insight["length_label"],
            insight["priority_score"],
            insight["priority_label"],
            insight["priority_reason"],
        ),
    )


def latest_sessions(limit: int = 12) -> list[dict[str, Any]]:
    candidate_limit = max(limit * 5, limit)
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
            (candidate_limit,),
        ).fetchall()

        sessions = [dict(row) for row in rows]
        cached_map = _load_cached_insights(conn, sessions)
        enriched_sessions: list[dict[str, Any]] = []

        for session in sessions:
            key = (session["source"], session["session_id"])
            cached = cached_map.get(key)
            if (
                cached
                and int(cached["latest_message_id"]) == int(session["latest_id"])
                and int(cached["message_count"]) == int(session["message_count"])
            ):
                session["topic_title"] = cached["topic_title"]
                session["topic_excerpt"] = cached["topic_excerpt"]
                session["tags"] = cached["tags"]
                session["length_label"] = cached["length_label"]
                session["priority_score"] = int(cached["priority_score"])
                session["priority_label"] = cached["priority_label"]
                session["priority_reason"] = cached["priority_reason"]
                session["insight_updated_at"] = cached["updated_at"]
                enriched_sessions.append(session)
                continue

            message_rows = conn.execute(
                """
                SELECT id, source, session_id, role, content, created_at, summary
                FROM messages
                WHERE source = ? AND session_id = ?
                ORDER BY id ASC
                """,
                (session["source"], session["session_id"]),
            ).fetchall()
            messages = [dict(message_row) for message_row in message_rows]
            insight = _build_session_insight(session=session, messages=messages)
            _cache_session_insight(conn, session, insight)

            session["topic_title"] = insight["topic_title"]
            session["topic_excerpt"] = insight["topic_excerpt"]
            session["tags"] = insight["tags"]
            session["length_label"] = insight["length_label"]
            session["priority_score"] = insight["priority_score"]
            session["priority_label"] = insight["priority_label"]
            session["priority_reason"] = insight["priority_reason"]
            enriched_sessions.append(session)

    enriched_sessions.sort(key=lambda item: (-int(item["priority_score"]), -int(item["latest_id"])))
    return enriched_sessions[:limit]


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
