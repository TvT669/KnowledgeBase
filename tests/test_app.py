from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


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

    notes_page = client.get("/notes")
    home_page = client.get("/")

    assert notes_page.status_code == 200
    assert "笔记检索" in notes_page.text
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

    assert update_resp.status_code == 200
    assert update_resp.json()["note"]["status"] == "reviewed"
    assert updated_search.status_code == 200
    assert any(item["id"] == note["id"] for item in updated_search.json()["items"])
    assert home_page.status_code == 200
    assert "整理工作台" in home_page.text
    assert "按会话整理" in home_page.text


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

    draft["title"] = f"会话笔记搜索 {token}"
    draft["key_takeaways"] = f"{draft['key_takeaways']} {token}"

    assert len(source_ids) == 3
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

    home_page = client.get("/")
    notes_page = client.get("/notes")

    assert source_resp.status_code == 200
    assert len(source_resp.json()["items"]) == 3
    assert note_search.status_code == 200
    assert any(item["id"] == note["id"] for item in note_search.json()["items"])
    assert home_page.status_code == 200
    assert "整理整个会话" in home_page.text
    assert notes_page.status_code == 200
    assert "查看来源对话" in notes_page.text
    assert "编辑笔记" in notes_page.text
