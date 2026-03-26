from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app
from app.services.sessions import latest_sessions


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ingest_duplicate_and_search() -> None:
    token = uuid4().hex[:8]
    payload = {
        "source": "pytest",
        "session_id": f"pytest-demo-session-{token}",
        "role": "assistant",
        "content": f"pytest 验证幂等写入和补偿搜索 {token}",
    }

    first = client.post("/api/ingest", json=payload)
    second = client.post("/api/ingest", json=payload)
    search = client.post("/api/search", json={"q": token, "limit": 10})

    assert first.status_code == 200
    assert second.status_code == 409
    assert search.status_code == 200
    assert any(item["session_id"] == payload["session_id"] for item in search.json()["items"])


def test_generate_and_save_note() -> None:
    token = uuid4().hex[:8]
    payload = {
        "source": "pytest",
        "session_id": f"pytest-note-session-{token}",
        "role": "assistant",
        "content": (
            f"由于缺少幂等键，重复重试会造成重复写入。"
            f"建议增加请求唯一键和失败补偿记录，避免再次发生。 {token}"
        ),
    }

    ingest = client.post("/api/ingest", json=payload)

    assert ingest.status_code == 200

    message_id = ingest.json()["id"]
    draft_resp = client.post("/api/notes/generate", json={"message_ids": [message_id]})

    assert draft_resp.status_code == 200

    draft = draft_resp.json()["draft"]
    draft["title"] = f"单条笔记搜索 {token}"
    draft["key_takeaways"] = f"{draft['key_takeaways']} {token}"
    assert draft["title"]
    assert draft["problem"]
    assert draft["root_cause"]
    assert draft["solution"]
    assert draft["key_takeaways"]

    save_resp = client.post(
        "/api/notes",
        json={
            **draft,
            "message_ids": [message_id],
            "status": "draft",
            "source_type": "mixed",
        },
    )

    assert save_resp.status_code == 200
    note = save_resp.json()["note"]
    assert note["source_count"] == 1

    note_search = client.post("/api/notes/search", json={"q": token, "limit": 10})
    inbox_resp = client.get("/api/inbox")

    notes_page = client.get("/notes")
    home_page = client.get("/")

    assert notes_page.status_code == 200
    assert "笔记检索" in notes_page.text
    assert "删除笔记" in notes_page.text
    assert inbox_resp.status_code == 200
    assert any(
        item["session_id"] == payload["session_id"]
        for item in inbox_resp.json()["groups"]["done"]
    )
    assert note_search.status_code == 200
    assert any(item["id"] == note["id"] for item in note_search.json()["items"])
    update_resp = client.put(
        f"/api/notes/{note['id']}",
        json={
            "title": f"单条笔记已更新 {token}",
            "problem": draft["problem"],
            "root_cause": draft["root_cause"],
            "solution": draft["solution"],
            "key_takeaways": draft["key_takeaways"],
            "status": "reviewed",
            "source_type": "mixed",
        },
    )
    updated_search = client.post("/api/notes/search", json={"q": f"已更新 {token}", "limit": 10})
    delete_resp = client.delete(f"/api/notes/{note['id']}")
    deleted_search = client.post("/api/notes/search", json={"q": token, "limit": 10})
    deleted_sources = client.get(f"/api/notes/{note['id']}/sources")
    inbox_after_delete = client.get("/api/inbox")

    assert update_resp.status_code == 200
    assert update_resp.json()["note"]["status"] == "reviewed"
    assert updated_search.status_code == 200
    assert any(item["id"] == note["id"] for item in updated_search.json()["items"])
    assert delete_resp.status_code == 200
    assert deleted_search.status_code == 200
    assert all(item["id"] != note["id"] for item in deleted_search.json()["items"])
    assert deleted_sources.status_code == 404
    assert inbox_after_delete.status_code == 200
    assert any(
        item["session_id"] == payload["session_id"] and item["status"] == "ready"
        for item in inbox_after_delete.json()["groups"]["ready"]
    )
    assert home_page.status_code == 200
    assert "知识收件箱" in home_page.text
    assert "建议先整理" in home_page.text
    assert "刷新收件箱" in home_page.text


def test_generate_and_save_note_from_session() -> None:
    token = uuid4().hex[:8]
    session_id = f"pytest-whole-session-{token}"
    messages = [
        {
            "source": "pytest",
            "session_id": session_id,
            "role": "user",
            "content": f"线上接口出现重复写入，怀疑和重试有关。 {token}",
        },
        {
            "source": "pytest",
            "session_id": session_id,
            "role": "assistant",
            "content": f"根因是没有幂等键，重复请求无法被识别。 {token}",
        },
        {
            "source": "pytest",
            "session_id": session_id,
            "role": "assistant",
            "content": f"解决方案是增加幂等键、服务端去重和失败补偿日志。 {token}",
        },
    ]

    for message in messages:
        ingest = client.post("/api/ingest", json=message)
        assert ingest.status_code == 200

    draft_resp = client.post(
        "/api/notes/generate/session",
        json={"source": "pytest", "session_id": session_id},
    )

    assert draft_resp.status_code == 200

    draft_payload = draft_resp.json()
    draft = draft_payload["draft"]
    source_ids = [item["id"] for item in draft_payload["sources"]]
    session_messages = client.get(
        "/api/sessions/messages",
        params={"source": "pytest", "session_id": session_id},
    )

    draft["title"] = f"会话笔记搜索 {token}"
    draft["key_takeaways"] = f"{draft['key_takeaways']} {token}"

    assert len(source_ids) == 3
    assert session_messages.status_code == 200
    assert len(session_messages.json()["items"]) == 3
    assert draft["title"]
    assert draft["problem"]
    assert draft["root_cause"]
    assert draft["solution"]
    assert draft["key_takeaways"]

    save_resp = client.post(
        "/api/notes",
        json={
            **draft,
            "message_ids": source_ids,
            "status": "draft",
            "source_type": "session",
        },
    )

    assert save_resp.status_code == 200
    note = save_resp.json()["note"]
    assert note["source_count"] == 3

    source_resp = client.get(f"/api/notes/{note['id']}/sources")
    note_search = client.post("/api/notes/search", json={"q": token, "limit": 10})
    inbox_resp = client.get("/api/inbox")

    home_page = client.get("/")
    notes_page = client.get("/notes")

    assert source_resp.status_code == 200
    assert len(source_resp.json()["items"]) == 3
    assert note_search.status_code == 200
    assert any(item["id"] == note["id"] for item in note_search.json()["items"])
    assert inbox_resp.status_code == 200
    assert any(
        item["session_id"] == session_id and item["status"] == "done"
        for item in inbox_resp.json()["groups"]["done"]
    )
    assert home_page.status_code == 200
    assert "知识收件箱" in home_page.text
    assert "查看完整记录" in home_page.text
    assert "确认建议" in home_page.text
    sessions = latest_sessions(limit=20)
    assert any(session["topic_title"] == "重试与幂等设计" for session in sessions)
    assert any(session["priority_label"] in {"推荐优先整理", "值得整理"} for session in sessions)
    with get_conn() as conn:
        cached = conn.execute(
            """
            SELECT topic_title, priority_label, latest_message_id
            FROM session_insights
            WHERE source = ? AND session_id = ?
            """,
            ("pytest", session_id),
        ).fetchone()
    assert cached is not None
    assert cached["topic_title"] == "重试与幂等设计"
    with get_conn() as conn:
        queued = conn.execute(
            """
            SELECT status, note_id
            FROM session_queue
            WHERE source = ? AND session_id = ?
            """,
            ("pytest", session_id),
        ).fetchone()
    assert queued is not None
    assert queued["status"] == "done"
    assert queued["note_id"] == note["id"]
    assert notes_page.status_code == 200
    assert "查看来源对话" in notes_page.text
    assert "编辑笔记" in notes_page.text


def test_inbox_state_transitions_preserve_manual_metadata() -> None:
    token = uuid4().hex[:8]
    session_id = f"pytest-inbox-session-{token}"
    messages = [
        {
            "source": "pytest",
            "session_id": session_id,
            "role": "user",
            "content": f"接口偶发重复写入，想判断是不是重试导致。{token}",
        },
        {
            "source": "pytest",
            "session_id": session_id,
            "role": "assistant",
            "content": f"根因是没有幂等键，请求被重复消费。{token}",
        },
        {
            "source": "pytest",
            "session_id": session_id,
            "role": "assistant",
            "content": f"建议补充幂等键、去重表和失败补偿日志。{token}",
        },
    ]

    for message in messages:
        ingest = client.post("/api/ingest", json=message)
        assert ingest.status_code == 200

    refresh_resp = client.post("/api/inbox/refresh")
    inbox_resp = client.get("/api/inbox?include_ignored=true")

    assert refresh_resp.status_code == 200
    assert inbox_resp.status_code == 200
    assert any(
        item["session_id"] == session_id
        for item in inbox_resp.json()["groups"]["ready"] + inbox_resp.json()["groups"]["new"]
    )

    confirm_resp = client.post(
        "/api/inbox/confirm",
        json={
            "source": "pytest",
            "session_id": session_id,
            "title": f"手动确认标题 {token}",
            "tags": ["幂等", "补偿"],
            "priority": "推荐优先整理",
        },
    )
    defer_resp = client.post(
        "/api/inbox/defer",
        json={"source": "pytest", "session_id": session_id},
    )
    ready_resp = client.post(
        "/api/inbox/ready",
        json={"source": "pytest", "session_id": session_id},
    )
    ignore_resp = client.post(
        "/api/inbox/ignore",
        json={"source": "pytest", "session_id": session_id},
    )
    inbox_with_ignored = client.get("/api/inbox?include_ignored=true")

    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["item"]["display_title"] == f"手动确认标题 {token}"
    assert confirm_resp.json()["item"]["display_tags"] == ["幂等", "补偿"]
    assert confirm_resp.json()["item"]["display_priority"] == "推荐优先整理"
    assert defer_resp.status_code == 200
    assert defer_resp.json()["item"]["status"] == "later"
    assert ready_resp.status_code == 200
    assert ready_resp.json()["item"]["status"] == "ready"
    assert ignore_resp.status_code == 200
    assert ignore_resp.json()["item"]["status"] == "ignored"
    assert inbox_with_ignored.status_code == 200
    assert any(
        item["session_id"] == session_id and item["display_title"] == f"手动确认标题 {token}"
        for item in inbox_with_ignored.json()["groups"]["ignored"]
    )


def test_generate_note_cleans_noisy_titles() -> None:
    token = uuid4().hex[:8]
    session_id = f"pytest-noisy-title-{token}"
    payload = {
        "source": "pytest",
        "session_id": session_id,
        "role": "assistant",
        "content": (
            f"/Users/bee/Desktop/demo/runtime/objc-runtime-new.h:794:37 "
            f"Expected identifier 问题怎么解决，这是一个常见的编译错误。 {token}"
        ),
    }

    ingest = client.post("/api/ingest", json=payload)

    assert ingest.status_code == 200

    draft_resp = client.post(
        "/api/notes/generate/session",
        json={"source": "pytest", "session_id": session_id},
    )

    assert draft_resp.status_code == 200

    draft = draft_resp.json()["draft"]
    assert draft["title"]
    assert "/Users/" not in draft["title"]
    assert "**" not in draft["title"]
    assert draft["title"] != "Expected identifier 问题怎么解决，这是一个常见的编译错误"


def test_quick_save_session_creates_single_draft_note() -> None:
    token = uuid4().hex[:8]
    session_id = f"pytest-quick-save-{token}"
    messages = [
        {
            "source": "pytest",
            "session_id": session_id,
            "role": "user",
            "content": f"接口出现重复写入，怀疑重试时没有做幂等控制。 {token}",
        },
        {
            "source": "pytest",
            "session_id": session_id,
            "role": "assistant",
            "content": f"根因是缺少幂等键和去重记录，所以重复请求被重复消费。 {token}",
        },
        {
            "source": "pytest",
            "session_id": session_id,
            "role": "assistant",
            "content": f"建议先把这段会话存成草稿，再补充成正式笔记。 {token}",
        },
    ]

    for message in messages:
        ingest = client.post("/api/ingest", json=message)
        assert ingest.status_code == 200

    first_save = client.post(
        "/api/notes/quick-save/session",
        json={"source": "pytest", "session_id": session_id},
    )
    second_save = client.post(
        "/api/notes/quick-save/session",
        json={"source": "pytest", "session_id": session_id},
    )
    inbox_resp = client.get("/api/inbox")
    home_page = client.get("/")
    focused_notes_page = client.get(f"/notes?note_id={first_save.json()['note']['id']}")

    assert first_save.status_code == 200
    assert first_save.json()["reused"] is False
    assert first_save.json()["note"]["status"] == "draft"
    assert first_save.json()["note"]["source_count"] == 3
    assert second_save.status_code == 200
    assert second_save.json()["reused"] is True
    assert second_save.json()["note"]["id"] == first_save.json()["note"]["id"]
    assert inbox_resp.status_code == 200
    assert any(
        item["session_id"] == session_id and item["status"] == "done"
        for item in inbox_resp.json()["groups"]["done"]
    )
    assert home_page.status_code == 200
    assert "今日建议" in home_page.text
    assert "一键存草稿" in home_page.text
    assert f"/notes?note_id={first_save.json()['note']['id']}" in home_page.text
    assert focused_notes_page.status_code == 200
    assert "这是刚存下来的草稿" in focused_notes_page.text
    assert "openRequestedNoteIfNeeded();" in focused_notes_page.text
