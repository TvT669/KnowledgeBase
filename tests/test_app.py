from __future__ import annotations

import io
import json
import re
import time
import zipfile
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import HOME_INBOX_LIMIT, app
from app.services.inbox import list_inbox_groups, refresh_inbox_if_needed
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


def test_ingest_batch_requires_token_when_configured(monkeypatch) -> None:
    token = uuid4().hex[:8]
    monkeypatch.setenv("KNOWLEDGE_API_TOKEN", f"secret-{token}")

    payload = {
        "items": [
            {
                "source": "pytest",
                "session_id": f"pytest-remote-{token}",
                "role": "user",
                "content": f"远端上传用户消息 {token}",
                "summary": f"远端上传用户消息 {token}",
            },
            {
                "source": "pytest",
                "session_id": f"pytest-remote-{token}",
                "role": "assistant",
                "content": f"远端上传助手消息 {token}",
                "summary": f"远端上传助手消息 {token}",
            },
        ]
    }

    unauthorized = client.post("/api/ingest/batch", json=payload)
    first = client.post(
        "/api/ingest/batch",
        json=payload,
        headers={"X-Knowledge-Token": f"secret-{token}"},
    )
    second = client.post(
        "/api/ingest/batch",
        json=payload,
        headers={"X-Knowledge-Token": f"secret-{token}"},
    )

    assert unauthorized.status_code == 401
    assert first.status_code == 200
    assert first.json()["inserted_count"] == 2
    assert first.json()["deduped_count"] == 0
    assert second.status_code == 200
    assert second.json()["inserted_count"] == 0
    assert second.json()["deduped_count"] == 2


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
            "tags": [f"幂等{token}", "补偿"],
            "status": "draft",
            "source_type": "mixed",
        },
    )

    assert save_resp.status_code == 200
    note = save_resp.json()["note"]
    assert note["source_count"] == 1
    assert f"幂等{token}" in note["tags"]

    note_search = client.post("/api/notes/search", json={"q": token, "limit": 10})
    inbox_resp = client.get("/api/inbox")

    notes_page = client.get("/notes")
    home_page = client.get("/")

    assert notes_page.status_code == 200
    assert "统一搜索" in notes_page.text
    assert "原始会话命中" in notes_page.text
    assert "追加预览" in notes_page.text
    assert "追加时间线" in notes_page.text
    assert "editAppendTimelineOverview" in notes_page.text
    assert "editAppendTimelineFilters" in notes_page.text
    assert "editAppendTimelineSearchInput" in notes_page.text
    assert "批量导出" in notes_page.text
    assert "批量导出 Markdown" in notes_page.text
    assert "业务标签" in notes_page.text
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
            "tags": [f"回放{token}", "补偿"],
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
    assert update_resp.json()["note"]["status_label"] == "已复核"
    assert f"回放{token}" in update_resp.json()["note"]["tags"]
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
    assert "相似笔记" in home_page.text
    assert "待完善草稿" in home_page.text
    assert "刷新收件箱" in home_page.text
    assert "自动同步" in home_page.text
    assert "立即同步 IDE 对话" in home_page.text


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
            "tags": [f"幂等{token}", "重试"],
            "status": "draft",
            "source_type": "session",
        },
    )

    assert save_resp.status_code == 200
    note = save_resp.json()["note"]
    assert note["source_count"] == 3
    assert f"幂等{token}" in note["tags"]

    source_resp = client.get(f"/api/notes/{note['id']}/sources")
    note_search = client.post("/api/notes/search", json={"q": token, "limit": 10})
    inbox_resp = client.get("/api/inbox")

    home_page = client.get("/")
    notes_page = client.get("/notes")
    home_script = client.get("/static/home.js")
    notes_script = client.get("/static/notes.js")

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
    assert home_script.status_code == 200
    assert "/api/notes/recommend" in home_script.text
    assert "pick-recommended-note" in home_script.text
    assert "查看完整记录" in home_script.text
    assert "确认建议" in home_script.text
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
    assert notes_script.status_code == 200
    assert "查看来源对话" in notes_script.text
    assert "/api/search" in notes_script.text
    assert "/api/sessions/messages" in notes_script.text
    assert "preview-append-search-session" in notes_script.text
    assert "appendPreviewShell" in notes_script.text
    assert "knowledgebase.notes.appendSummary." in notes_script.text
    assert "editAppendSummarySections" in notes_script.text
    assert "field-highlight" in notes_script.text
    assert "/history" in notes_script.text
    assert "/export.md" in notes_script.text
    assert "/api/notes/export.zip" in notes_script.text
    assert "note-select-toggle" in notes_script.text
    assert "open-append-history-session" in notes_script.text
    assert "/undo" in notes_script.text
    assert "undo-append-history-event" in notes_script.text
    assert "focus-append-history-event" in notes_script.text
    assert "focusAppendTimelineEvent(" in notes_script.text
    assert "toggle-append-history-event" in notes_script.text
    assert "activeAppendTimelineExpandedIds" in notes_script.text
    assert "没有新增可并入内容" in notes_script.text
    assert "appendTimelineDateGroups" in notes_script.text
    assert "renderAppendTimelineOverview(" in notes_script.text
    assert "activeAppendTimelineQuery" in notes_script.text
    assert "editAppendTimelineSearchResetBtn" in notes_script.text
    assert "data-append-timeline-filter" in notes_script.text
    assert "appendTimelineFilterMeta" in notes_script.text
    assert "/api/notes/quick-append/session" in notes_script.text
    assert "quick-append-search-session" in notes_script.text
    assert "/api/notes/quick-save/session" in notes_script.text
    assert "quick-save-search-session" in notes_script.text
    assert "compose_source" in notes_script.text


def test_ide_sync_endpoint_imports_chat_file_and_updates_status(monkeypatch, tmp_path) -> None:
    token = uuid4().hex[:8]
    chat_file = tmp_path / f"sync-{token}.json"
    chat_file.write_text(
        json.dumps(
            {
                "requests": [
                    {
                        "message": {"text": f"同步入口测试用户消息 {token}"},
                        "response": [{"value": f"同步入口测试助手回复 {token}"}],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("app.services.ide_sync.discover_vscode_chat_files", lambda home: [chat_file])
    monkeypatch.setattr("app.services.ide_sync.discover_windsurf_chat_files", lambda home: [])

    sync_resp = client.post(
        "/api/sync/ide",
        json={"include_vscode": True, "include_windsurf": False, "wait": True},
    )
    status_resp = client.get("/api/sync/ide/status")
    search_resp = client.post("/api/search", json={"q": token, "limit": 10})

    assert sync_resp.status_code == 200
    assert sync_resp.json()["sync"]["files"] == 1
    assert sync_resp.json()["sync"]["parsed"] == 2
    assert sync_resp.json()["sync"]["inserted"] == 2
    assert sync_resp.json()["sync"]["selected_sources"]["include_vscode"] is True
    assert sync_resp.json()["sync"]["selected_sources"]["include_windsurf"] is False
    assert sync_resp.json()["refresh"]["scanned"] >= 1
    assert status_resp.status_code == 200
    assert status_resp.json()["state"]["last_result"]["files"] == 1
    assert status_resp.json()["state"]["last_options"]["include_vscode"] is True
    assert status_resp.json()["state"]["last_options"]["include_windsurf"] is False
    assert search_resp.status_code == 200
    assert len(search_resp.json()["items"]) >= 2


def test_ide_sync_endpoint_starts_background_job_by_default(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_start_ide_sync(*, include_vscode: bool, include_windsurf: bool, use_llm_summary: bool, home=None):
        captured["include_vscode"] = include_vscode
        captured["include_windsurf"] = include_windsurf
        captured["use_llm_summary"] = use_llm_summary
        return {
            "running": True,
            "last_started_at": "2026-03-31 10:00:00",
            "last_finished_at": "",
            "last_error": "",
            "last_result": None,
            "last_options": {
                "include_vscode": include_vscode,
                "include_windsurf": include_windsurf,
            },
            "progress": {
                "total_files": 0,
                "processed_files": 0,
                "parsed_messages": 0,
                "inserted_messages": 0,
                "current_source": "",
                "current_file": "",
            },
        }

    monkeypatch.setattr("app.main.start_ide_sync", fake_start_ide_sync)

    sync_resp = client.post("/api/sync/ide", json={"include_vscode": True, "include_windsurf": False})

    assert sync_resp.status_code == 202
    assert sync_resp.json()["status"] == "started"
    assert sync_resp.json()["state"]["running"] is True
    assert sync_resp.json()["state"]["last_options"]["include_vscode"] is True
    assert sync_resp.json()["state"]["last_options"]["include_windsurf"] is False
    assert captured == {
        "include_vscode": True,
        "include_windsurf": False,
        "use_llm_summary": False,
    }


def test_ide_sync_skips_already_synced_files(monkeypatch, tmp_path) -> None:
    token = uuid4().hex[:8]
    chat_file = tmp_path / f"skip-sync-{token}.json"
    chat_file.write_text(
        json.dumps(
            {
                "requests": [
                    {
                        "message": {"text": f"已同步文件用户消息 {token}"},
                        "response": [{"value": f"已同步文件助手消息 {token}"}],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("app.services.ide_sync.discover_vscode_chat_files", lambda home: [chat_file])
    monkeypatch.setattr("app.services.ide_sync.discover_windsurf_chat_files", lambda home: [])

    first_sync = client.post(
        "/api/sync/ide",
        json={"include_vscode": True, "include_windsurf": False, "wait": True},
    )
    second_sync = client.post(
        "/api/sync/ide",
        json={"include_vscode": True, "include_windsurf": False, "wait": True},
    )

    assert first_sync.status_code == 200
    assert first_sync.json()["sync"]["inserted"] == 2
    assert first_sync.json()["sync"]["skipped_files"] == 0
    assert second_sync.status_code == 200
    assert second_sync.json()["sync"]["inserted"] == 0
    assert second_sync.json()["sync"]["parsed"] == 0
    assert second_sync.json()["sync"]["skipped_files"] == 1


def test_ide_sync_status_remains_responsive_while_background_sync_runs(monkeypatch, tmp_path) -> None:
    import asyncio
    import app.services.ide_sync as ide_sync

    token = uuid4().hex[:8]
    chat_files = [tmp_path / f"slow-sync-{token}-1.json", tmp_path / f"slow-sync-{token}-2.json"]
    for chat_file in chat_files:
        chat_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("app.services.ide_sync.discover_vscode_chat_files", lambda home: chat_files)
    monkeypatch.setattr("app.services.ide_sync.discover_windsurf_chat_files", lambda home: [])

    def slow_load_messages_from_chat_file(file_path, source):
        time.sleep(0.25)
        return [
            {
                "source": source,
                "session_id": file_path.stem,
                "role": "user",
                "content": f"慢同步测试用户消息 {file_path.stem}",
            },
            {
                "source": source,
                "session_id": file_path.stem,
                "role": "assistant",
                "content": f"慢同步测试助手消息 {file_path.stem}",
            },
        ]

    monkeypatch.setattr("app.services.ide_sync.load_messages_from_chat_file", slow_load_messages_from_chat_file)

    async def run_case() -> dict:
        start_state = ide_sync.start_ide_sync(include_vscode=True, include_windsurf=False, home=tmp_path)
        assert start_state["running"] is True

        await asyncio.sleep(0.05)
        mid_state = ide_sync.get_ide_sync_state()
        assert mid_state["running"] is True
        assert mid_state["progress"]["total_files"] == 2
        assert mid_state["progress"]["processed_files"] < 2

        for _ in range(30):
            await asyncio.sleep(0.1)
            final_state = ide_sync.get_ide_sync_state()
            if not final_state["running"]:
                return final_state
        return ide_sync.get_ide_sync_state()

    final_state = asyncio.run(run_case())

    assert final_state["running"] is False
    assert final_state["last_result"]["files"] == 2


def test_append_to_existing_note_merges_sources_and_tags() -> None:
    token = uuid4().hex[:8]
    first_payload = {
        "source": "pytest",
        "session_id": f"pytest-append-a-{token}",
        "role": "assistant",
        "content": f"第一段结论：需要先补上幂等键。 {token}",
    }
    second_messages = [
        {
            "source": "pytest",
            "session_id": f"pytest-append-b-{token}",
            "role": "user",
            "content": f"后续补充：失败时还要落补偿日志。 {token}",
        },
        {
            "source": "pytest",
            "session_id": f"pytest-append-b-{token}",
            "role": "assistant",
            "content": f"建议把补偿回放链路也纳入排查清单。 {token}",
        },
    ]

    first_ingest = client.post("/api/ingest", json=first_payload)
    assert first_ingest.status_code == 200
    first_note_resp = client.post(
        "/api/notes",
        json={
            "title": f"归并笔记 {token}",
            "problem": f"出现重复写入，需要补齐上下文。 {token}",
            "root_cause": "缺少幂等键。",
            "solution": "先补幂等键，再观察重试行为。",
            "key_takeaways": "一篇笔记可以持续追加后续发现。",
            "message_ids": [first_ingest.json()["id"]],
            "tags": [f"初始{token}", "幂等"],
            "status": "reviewed",
            "source_type": "mixed",
        },
    )
    assert first_note_resp.status_code == 200
    first_note = first_note_resp.json()["note"]
    assert first_note["status"] == "reviewed"
    second_ids: list[int] = []
    for message in second_messages:
        ingest = client.post("/api/ingest", json=message)
        assert ingest.status_code == 200
        second_ids.append(int(ingest.json()["id"]))

    append_resp = client.post(
        "/api/notes",
        json={
            "title": f"忽略这个标题 {token}",
            "problem": f"新增补充问题描述。 {token}",
            "root_cause": "重试失败时没有完整补偿记录。",
            "solution": "追加补偿日志，并保留回放路径。",
            "key_takeaways": f"补充结论也应该继续沉淀。 {token}",
            "message_ids": second_ids,
            "existing_note_id": first_note["id"],
            "tags": [f"补充{token}", "补偿"],
            "status": "draft",
            "source_type": "session",
        },
    )
    source_resp = client.get(f"/api/notes/{first_note['id']}/sources")
    history_resp = client.get(f"/api/notes/{first_note['id']}/history")
    tag_search = client.post("/api/notes/search", json={"q": f"补充{token}", "limit": 10})
    inbox_resp = client.get("/api/inbox")

    assert append_resp.status_code == 200
    appended = append_resp.json()["note"]
    assert appended["id"] == first_note["id"]
    assert appended["title"] == first_note["title"]
    assert appended["status"] == "draft"
    assert appended["source_count"] == 3
    assert f"初始{token}" in appended["tags"]
    assert f"补充{token}" in appended["tags"]
    assert token in appended["key_takeaways"]
    assert append_resp.json()["append_summary"]["source_count_added"] == 2
    assert "关键收获" in append_resp.json()["append_summary"]["changed_sections"]
    assert append_resp.json()["append_summary"]["can_append"] is True
    assert any(
        item["field"] == "key_takeaways" and token in item["incoming_text"]
        for item in append_resp.json()["append_summary"]["section_updates"]
    )
    assert source_resp.status_code == 200
    assert len(source_resp.json()["items"]) == 3
    assert history_resp.status_code == 200
    assert len(history_resp.json()["items"]) == 1
    assert history_resp.json()["items"][0]["session_id"] == second_messages[0]["session_id"]
    assert history_resp.json()["items"][0]["summary_text"]
    assert history_resp.json()["items"][0]["section_updates"]
    assert history_resp.json()["items"][0]["can_undo"] is True
    assert tag_search.status_code == 200
    assert any(item["id"] == first_note["id"] for item in tag_search.json()["items"])
    assert inbox_resp.status_code == 200
    assert any(
        item["session_id"] == second_messages[0]["session_id"] and item["note_id"] == first_note["id"]
        for item in inbox_resp.json()["groups"]["done"]
    )


def test_note_recommend_returns_similar_existing_note() -> None:
    token = uuid4().hex[:8]
    ingest = client.post(
        "/api/ingest",
        json={
            "source": "pytest",
            "session_id": f"pytest-recommend-session-{token}",
            "role": "assistant",
            "content": f"需要处理接口重试导致的重复写入，并补上幂等键和补偿日志。 {token}",
        },
    )
    assert ingest.status_code == 200

    save_resp = client.post(
        "/api/notes",
        json={
            "title": f"重试与幂等排查 {token}",
            "problem": "接口重试后出现重复写入。",
            "root_cause": "没有幂等键，请求被重复消费。",
            "solution": "增加幂等键与补偿日志。",
            "key_takeaways": "同主题的排查结论适合持续追加到同一篇笔记。",
            "message_ids": [ingest.json()["id"]],
            "tags": [f"幂等{token}", "补偿"],
            "status": "reviewed",
            "source_type": "mixed",
        },
    )
    assert save_resp.status_code == 200
    note = save_resp.json()["note"]

    recommend_resp = client.post(
        "/api/notes/recommend",
        json={
            "title": "重复写入与幂等补充",
            "problem": f"最近又遇到重复写入问题。 {token}",
            "root_cause": "怀疑还是缺少幂等键。",
            "solution": "继续补充补偿日志。",
            "key_takeaways": "同一主题适合直接追加。",
            "tags": [f"幂等{token}", "补偿"],
            "limit": 5,
        },
    )

    assert recommend_resp.status_code == 200
    items = recommend_resp.json()["items"]
    assert items
    assert items[0]["id"] == note["id"]
    assert f"幂等{token}" in items[0]["tags"]
    assert items[0]["match_reason"]


def test_noop_append_is_blocked() -> None:
    token = uuid4().hex[:8]
    payload = {
        "source": "pytest",
        "session_id": f"pytest-noop-append-{token}",
        "role": "assistant",
        "content": f"先补幂等键，避免重复写入。 {token}",
    }

    ingest = client.post("/api/ingest", json=payload)
    assert ingest.status_code == 200
    message_id = ingest.json()["id"]

    create_resp = client.post(
        "/api/notes",
        json={
            "title": f"空追加测试 {token}",
            "problem": "接口重试导致重复写入。",
            "root_cause": "缺少幂等键。",
            "solution": "补幂等键。",
            "key_takeaways": f"先建立基础结论。 {token}",
            "message_ids": [message_id],
            "tags": [f"幂等{token}"],
            "status": "reviewed",
            "source_type": "mixed",
        },
    )
    assert create_resp.status_code == 200
    note = create_resp.json()["note"]

    noop_resp = client.post(
        "/api/notes",
        json={
            "title": f"忽略 {token}",
            "problem": "接口重试导致重复写入。",
            "root_cause": "缺少幂等键。",
            "solution": "补幂等键。",
            "key_takeaways": f"先建立基础结论。 {token}",
            "message_ids": [message_id],
            "existing_note_id": note["id"],
            "tags": [f"幂等{token}"],
            "status": "draft",
            "source_type": "mixed",
        },
    )
    history_resp = client.get(f"/api/notes/{note['id']}/history")
    source_resp = client.get(f"/api/notes/{note['id']}/sources")

    assert noop_resp.status_code == 409
    assert noop_resp.json()["detail"] == "没有检测到新的来源或新增段落，这次追加已拦截。"
    assert history_resp.status_code == 200
    assert history_resp.json()["items"] == []
    assert source_resp.status_code == 200
    assert len(source_resp.json()["items"]) == 1


def test_note_markdown_export_returns_attachment() -> None:
    token = uuid4().hex[:8]
    payload = {
        "source": "pytest",
        "session_id": f"pytest-export-{token}",
        "role": "assistant",
        "content": f"导出 Markdown 测试内容，包含幂等和补偿结论。 {token}",
    }

    ingest = client.post("/api/ingest", json=payload)
    assert ingest.status_code == 200

    save_resp = client.post(
        "/api/notes",
        json={
            "title": f"导出测试笔记 {token}",
            "problem": "需要把笔记导出成 Markdown。",
            "root_cause": "系统外也要复用知识内容。",
            "solution": "提供 Markdown 下载能力。",
            "key_takeaways": f"导出后可继续在别处复用。 {token}",
            "message_ids": [ingest.json()["id"]],
            "tags": [f"导出{token}", "Markdown"],
            "status": "reviewed",
            "source_type": "mixed",
        },
    )
    assert save_resp.status_code == 200
    note = save_resp.json()["note"]

    export_resp = client.get(f"/api/notes/{note['id']}/export.md")

    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"].startswith("text/markdown")
    assert "attachment;" in export_resp.headers["content-disposition"]
    assert f"# {note['title']}" in export_resp.text
    assert "## 问题描述" in export_resp.text
    assert "## 来源对话" in export_resp.text
    assert token in export_resp.text


def test_note_batch_markdown_export_returns_zip() -> None:
    token = uuid4().hex[:8]
    note_ids: list[int] = []

    for index in range(2):
        payload = {
            "source": "pytest",
            "session_id": f"pytest-batch-export-{token}-{index}",
            "role": "assistant",
            "content": f"批量导出 Markdown 测试内容 {index}。 {token}",
        }
        ingest = client.post("/api/ingest", json=payload)
        assert ingest.status_code == 200
        save_resp = client.post(
            "/api/notes",
            json={
                "title": f"批量导出笔记 {token} {index}",
                "problem": "需要批量导出笔记。",
                "root_cause": "系统外也会复用多篇知识内容。",
                "solution": "把多篇笔记打包成 zip 下载。",
                "key_takeaways": f"第 {index + 1} 篇批量导出内容。 {token}",
                "message_ids": [ingest.json()["id"]],
                "tags": [f"批量导出{token}"],
                "status": "reviewed",
                "source_type": "mixed",
            },
        )
        assert save_resp.status_code == 200
        note_ids.append(int(save_resp.json()["note"]["id"]))

    export_resp = client.post("/api/notes/export.zip", json={"note_ids": note_ids})

    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"] == "application/zip"
    assert "attachment;" in export_resp.headers["content-disposition"]

    archive = zipfile.ZipFile(io.BytesIO(export_resp.content))
    names = archive.namelist()
    assert len(names) == 2
    exported = archive.read(names[0]).decode("utf-8")
    assert "# 批量导出笔记" in exported
    assert "## 来源对话" in exported
    assert token in exported


def test_undo_latest_append_restores_note_state() -> None:
    token = uuid4().hex[:8]
    base_payload = {
        "source": "pytest",
        "session_id": f"pytest-undo-base-{token}",
        "role": "assistant",
        "content": f"先补幂等键，避免重复写入。 {token}",
    }
    append_messages = [
        {
            "source": "pytest",
            "session_id": f"pytest-undo-session-{token}",
            "role": "user",
            "content": f"这次要补上补偿日志和回放链路。 {token}",
        },
        {
            "source": "pytest",
            "session_id": f"pytest-undo-session-{token}",
            "role": "assistant",
            "content": f"建议把补偿回放结论并进已有笔记。 {token}",
        },
    ]

    base_ingest = client.post("/api/ingest", json=base_payload)
    assert base_ingest.status_code == 200
    base_note_resp = client.post(
        "/api/notes",
        json={
            "title": f"撤销测试笔记 {token}",
            "problem": "接口重试导致重复写入。",
            "root_cause": "缺少幂等键。",
            "solution": "补幂等键。",
            "key_takeaways": "先建立基础笔记。",
            "message_ids": [base_ingest.json()["id"]],
            "tags": [f"幂等{token}"],
            "status": "reviewed",
            "source_type": "mixed",
        },
    )
    assert base_note_resp.status_code == 200
    note = base_note_resp.json()["note"]

    append_ids: list[int] = []
    for message in append_messages:
        ingest = client.post("/api/ingest", json=message)
        assert ingest.status_code == 200
        append_ids.append(int(ingest.json()["id"]))

    append_resp = client.post(
        "/api/notes",
        json={
            "title": f"忽略 {token}",
            "problem": f"补充问题描述 {token}",
            "root_cause": "重试失败时没有补偿日志。",
            "solution": "补上补偿日志和回放链路。",
            "key_takeaways": f"补偿结论也要沉淀 {token}",
            "message_ids": append_ids,
            "existing_note_id": note["id"],
            "tags": [f"补偿{token}"],
            "status": "draft",
            "source_type": "session",
        },
    )
    assert append_resp.status_code == 200

    history_resp = client.get(f"/api/notes/{note['id']}/history")
    assert history_resp.status_code == 200
    history_items = history_resp.json()["items"]
    assert len(history_items) == 1
    event_id = history_items[0]["id"]
    assert history_items[0]["can_undo"] is True

    undo_resp = client.post(f"/api/notes/{note['id']}/history/{event_id}/undo")
    inbox_resp = client.get("/api/inbox")
    history_after_undo = client.get(f"/api/notes/{note['id']}/history")

    assert undo_resp.status_code == 200
    undone_note = undo_resp.json()["note"]
    assert undone_note["id"] == note["id"]
    assert undone_note["status"] == "reviewed"
    assert undone_note["source_count"] == 1
    assert f"补偿{token}" not in undone_note["tags"]
    assert token not in undone_note["key_takeaways"]
    assert history_after_undo.status_code == 200
    assert history_after_undo.json()["items"] == []
    assert inbox_resp.status_code == 200
    assert any(
        item["session_id"] == append_messages[0]["session_id"] and item["status"] == "ready" and not item["note_id"]
        for item in inbox_resp.json()["groups"]["ready"]
    )


def test_quick_append_session_appends_to_recommended_note() -> None:
    token = uuid4().hex[:8]
    base_message = {
        "source": "pytest",
        "session_id": f"pytest-quick-append-base-{token}",
        "role": "assistant",
        "content": f"需要补上幂等键和补偿日志，避免重复写入。 {token}",
    }
    append_messages = [
        {
            "source": "pytest",
            "session_id": f"pytest-quick-append-session-{token}",
            "role": "user",
            "content": f"这次还是重复写入问题，怀疑重试补偿链路没兜住。 {token}",
        },
        {
            "source": "pytest",
            "session_id": f"pytest-quick-append-session-{token}",
            "role": "assistant",
            "content": f"建议继续补充补偿日志和回放链路说明。 {token}",
        },
    ]

    base_ingest = client.post("/api/ingest", json=base_message)
    assert base_ingest.status_code == 200
    base_note_resp = client.post(
        "/api/notes",
        json={
            "title": f"幂等补偿总笔记 {token}",
            "problem": "接口重试导致重复写入。",
            "root_cause": "缺少幂等键。",
            "solution": "补充幂等键和补偿日志。",
            "key_takeaways": "同主题问题持续追加到一篇笔记。",
            "message_ids": [base_ingest.json()["id"]],
            "tags": [f"幂等{token}", "补偿"],
            "status": "reviewed",
            "source_type": "mixed",
        },
    )
    assert base_note_resp.status_code == 200
    base_note = base_note_resp.json()["note"]

    for message in append_messages:
        ingest = client.post("/api/ingest", json=message)
        assert ingest.status_code == 200

    confirm_resp = client.post(
        "/api/inbox/confirm",
        json={
            "source": "pytest",
            "session_id": append_messages[0]["session_id"],
            "title": f"重复写入补充 {token}",
            "tags": [f"幂等{token}", "补偿"],
            "priority": "推荐优先整理",
        },
    )
    assert confirm_resp.status_code == 200

    append_resp = client.post(
        "/api/notes/quick-append/session",
        json={
            "source": "pytest",
            "session_id": append_messages[0]["session_id"],
            "note_id": base_note["id"],
        },
    )
    source_resp = client.get(f"/api/notes/{base_note['id']}/sources")
    inbox_resp = client.get("/api/inbox")

    assert append_resp.status_code == 200
    assert append_resp.json()["reused"] is False
    note = append_resp.json()["note"]
    assert note["id"] == base_note["id"]
    assert note["status"] == "draft"
    assert note["source_count"] == 3
    assert "补偿" in note["solution"] or "补偿" in note["key_takeaways"]
    assert f"幂等{token}" in note["tags"]
    assert append_resp.json()["append_summary"]["source_count_added"] == 2
    assert append_resp.json()["append_summary"]["summary_text"]
    assert append_resp.json()["append_summary"]["section_updates"]
    assert source_resp.status_code == 200
    assert len(source_resp.json()["items"]) == 3
    assert inbox_resp.status_code == 200
    assert any(
        item["session_id"] == append_messages[0]["session_id"] and item["note_id"] == base_note["id"]
        for item in inbox_resp.json()["groups"]["done"]
    )


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

    confirm_resp = client.post(
        "/api/inbox/confirm",
        json={
            "source": "pytest",
            "session_id": session_id,
            "title": f"快速草稿 {token}",
            "tags": [f"草稿{token}", "幂等"],
            "priority": "推荐优先整理",
        },
    )
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
    notes_script = client.get("/static/notes.js")
    home_script = client.get("/static/home.js")

    assert confirm_resp.status_code == 200
    assert first_save.status_code == 200
    assert first_save.json()["reused"] is False
    assert first_save.json()["note"]["status"] == "draft"
    assert first_save.json()["note"]["status_label"] == "草稿"
    assert first_save.json()["note"]["source_count"] == 3
    assert f"草稿{token}" in first_save.json()["note"]["tags"]
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
    assert home_script.status_code == 200
    assert "一键存草稿" in home_script.text
    assert f"/notes?note_id={first_save.json()['note']['id']}" in home_page.text
    assert focused_notes_page.status_code == 200
    assert 'id="notesPageBootstrap"' in focused_notes_page.text
    assert '/static/notes.js' in focused_notes_page.text
    assert notes_script.status_code == 200
    assert "这是刚存下来的草稿" in notes_script.text
    assert "openRequestedNoteIfNeeded();" in notes_script.text


def test_notes_detect_stack_tags_and_render_stack_filter() -> None:
    token = uuid4().hex[:8]
    session_id = f"pytest-stack-note-{token}"
    message = {
        "source": "pytest",
        "session_id": session_id,
        "role": "assistant",
        "content": f"FastAPI 使用 Pydantic 校验请求，并通过 SQLite FTS5 提供本地搜索。 {token}",
    }

    ingest = client.post("/api/ingest", json=message)

    assert ingest.status_code == 200

    message_id = ingest.json()["id"]
    save_resp = client.post(
        "/api/notes",
        json={
            "title": f"FastAPI + SQLite 分类验证 {token}",
            "problem": "FastAPI 接口需要做请求校验。",
            "root_cause": "Pydantic 模型与 SQLite FTS5 的字段设计没有对齐。",
            "solution": "在 FastAPI 服务中同步更新 Pydantic 模型，并检查 SQLite FTS5 建表与索引。",
            "key_takeaways": "FastAPI 很适合本地工具接口，SQLite FTS5 适合做轻量搜索。",
            "message_ids": [message_id],
            "status": "draft",
            "source_type": "mixed",
        },
    )
    search_resp = client.post("/api/notes/search", json={"q": token, "limit": 10})
    notes_page = client.get("/notes")
    notes_script = client.get("/static/notes.js")

    assert save_resp.status_code == 200
    note = save_resp.json()["note"]
    assert "FastAPI" in note["stack_tags"]
    assert "SQLite" in note["stack_tags"]
    assert search_resp.status_code == 200
    matched = next(item for item in search_resp.json()["items"] if item["id"] == note["id"])
    assert "FastAPI" in matched["stack_tags"]
    assert "SQLite" in matched["stack_tags"]
    assert notes_page.status_code == 200
    assert "技术栈筛选" in notes_page.text
    assert "原始会话命中" in notes_page.text
    assert "追加预览" in notes_page.text
    assert "追加时间线" in notes_page.text
    assert "editAppendTimelineFilters" in notes_page.text
    assert "stackFilterList" in notes_page.text
    assert "笔记状态" in notes_page.text
    assert "statusFilterList" in notes_page.text
    assert 'id="notesPageBootstrap"' in notes_page.text
    assert '/static/notes.js' in notes_page.text
    assert notes_script.status_code == 200
    assert "sessionSearchSection" in notes_script.text
    assert "open-session-search-result" in notes_script.text
    assert "openAppendPreview(" in notes_script.text
    assert "knowledgebase.notes.filters" in notes_script.text
    assert "knowledgebase.notes.editDraft." in notes_script.text
    assert "search-hit" in notes_script.text
    assert "草稿" in notes_script.text
    assert "已复核" in notes_script.text
    assert "已发布" in notes_script.text
    assert matched["status_label"] == "草稿"


def test_inbox_refresh_only_when_needed() -> None:
    baseline = refresh_inbox_if_needed(limit=40, max_age_seconds=3600)
    second = refresh_inbox_if_needed(limit=40, max_age_seconds=3600)

    assert baseline["state"]["needs_refresh"] is False
    assert second["refreshed"] is False
    assert second["reason"] == "fresh"

    token = uuid4().hex[:8]
    ingest = client.post(
        "/api/ingest",
        json={
            "source": "pytest",
            "session_id": f"pytest-conditional-refresh-{token}",
            "role": "assistant",
            "content": f"新增会话应该触发一次自动刷新。 {token}",
        },
    )

    assert ingest.status_code == 200

    with_new_messages = refresh_inbox_if_needed(limit=40, max_age_seconds=3600)

    assert with_new_messages["refreshed"] is True
    assert with_new_messages["reason"] == "new_messages"

    with get_conn() as conn:
        conn.execute("UPDATE session_queue SET updated_at = '2000-01-01 00:00:00'")

    stale_refresh = refresh_inbox_if_needed(limit=40, max_age_seconds=60)

    assert stale_refresh["refreshed"] is True
    assert stale_refresh["reason"] == "stale"


def test_inbox_search_looks_past_default_group_limit() -> None:
    token = uuid4().hex[:8]
    target_session_id = f"pytest-inbox-search-target-{token}"
    target_query = f"search-target-{token}"

    def create_ready_session(session_id: str, marker: str) -> None:
        messages = [
            {
                "source": "pytest",
                "session_id": session_id,
                "role": "user",
                "content": f"线上出现重复写入，怀疑和重试没有做幂等控制有关。 {marker}",
            },
            {
                "source": "pytest",
                "session_id": session_id,
                "role": "assistant",
                "content": f"根因是缺少幂等键，请求重试后被重复消费。 {marker}",
            },
            {
                "source": "pytest",
                "session_id": session_id,
                "role": "assistant",
                "content": f"建议补充幂等键、去重记录和失败补偿日志。 {marker}",
            },
        ]

        for message in messages:
            ingest = client.post("/api/ingest", json=message)
            assert ingest.status_code == 200

    create_ready_session(target_session_id, target_query)
    for index in range(13):
        create_ready_session(
            f"pytest-inbox-search-filler-{token}-{index}",
            f"search-filler-{token}-{index}",
        )

    refresh_resp = client.post("/api/inbox/refresh")
    default_inbox = client.get("/api/inbox", params={"limit_per_group": 12})
    search_inbox = client.get(
        "/api/inbox",
        params={"limit_per_group": 12, "q": target_query},
    )

    assert refresh_resp.status_code == 200
    assert default_inbox.status_code == 200
    assert search_inbox.status_code == 200

    default_session_ids = {
        item["session_id"]
        for items in default_inbox.json()["groups"].values()
        for item in items
    }
    matched_session_ids = {
        item["session_id"]
        for items in search_inbox.json()["groups"].values()
        for item in items
    }

    assert target_session_id not in default_session_ids
    assert matched_session_ids == {target_session_id}


def test_home_page_pending_metrics_match_displayed_groups() -> None:
    token = uuid4().hex[:8]

    for index in range(14):
        session_id = f"pytest-home-metrics-{token}-{index}"
        messages = [
            {
                "source": "pytest",
                "session_id": session_id,
                "role": "user",
                "content": f"这是一条待处理会话，需要后续整理。 {token}-{index}",
            },
            {
                "source": "pytest",
                "session_id": session_id,
                "role": "assistant",
                "content": f"建议沉淀成笔记，后续继续补充。 {token}-{index}",
            },
        ]
        for message in messages:
            ingest = client.post("/api/ingest", json=message)
            assert ingest.status_code == 200

    refresh_resp = client.post("/api/inbox/refresh")
    inbox_data = list_inbox_groups(limit_per_group=HOME_INBOX_LIMIT)
    home_page = client.get("/")

    assert refresh_resp.status_code == 200
    assert home_page.status_code == 200

    pending_metric = re.search(r'id="pendingMetric"[^>]*>(\d+)<', home_page.text)
    ready_metric = re.search(r'id="readyMetric"[^>]*>(\d+)<', home_page.text)

    assert pending_metric is not None
    assert ready_metric is not None
    assert pending_metric.group(1) == str(len(inbox_data["groups"]["ready"]) + len(inbox_data["groups"]["new"]))
    assert ready_metric.group(1) == str(len(inbox_data["groups"]["ready"]))


def test_home_page_uses_versioned_assets() -> None:
    home_page = client.get("/")

    assert home_page.status_code == 200
    assert '/static/style.css?v=' in home_page.text
    assert '/static/home.js?v=' in home_page.text


def test_home_page_renders_workspace_status_filters() -> None:
    home_page = client.get("/")
    home_script = client.get("/static/home.js")

    assert home_page.status_code == 200
    assert "同步" in home_page.text
    assert "自动同步" in home_page.text
    assert "立即同步 IDE 对话" in home_page.text
    assert "同步来源" in home_page.text
    assert "状态筛选" in home_page.text
    assert "批量处理" in home_page.text
    assert "批量一键存草稿" in home_page.text
    assert "批量确认建议" in home_page.text
    assert "批量稍后" in home_page.text
    assert "批量忽略" in home_page.text
    assert "workspaceFilterList" in home_page.text
    assert "显示已忽略" in home_page.text
    assert 'id="homePageBootstrap"' in home_page.text
    assert '/static/home.js' in home_page.text
    assert home_script.status_code == 200
    assert "/api/sync/ide" in home_script.text
    assert "/api/inbox/batch" in home_script.text
    assert "session-select-toggle" in home_script.text
    assert "quick_save" in home_script.text
    assert "batchConfirmShell" in home_script.text
    assert "knowledgebase.home.autoSync" in home_script.text
    assert "knowledgebase.home.syncSources" in home_script.text
    assert "data-sync-source" in home_script.text
    assert "VSCode" in home_script.text
    assert "Windsurf" in home_script.text
    assert "knowledgebase.home.workspace" in home_script.text
    assert "knowledgebase.home.composerDraft" in home_script.text
    assert "knowledgebase.notes.appendSummary." in home_script.text
    assert "compose_source" in home_script.text
    assert "compose_session_id" in home_script.text
    assert "state.workspaceQuery" in home_script.text
    assert "params.set('q', state.workspaceQuery)" in home_script.text
    assert "正在搜索收件箱" in home_script.text
    assert "建议先整理" in home_script.text
    assert "待判断" in home_script.text
    assert "稍后处理" in home_script.text
    assert "最近完成" in home_script.text
    assert "encodeURIComponent(noteId)" in home_script.text


def test_inbox_batch_actions_update_multiple_sessions() -> None:
    token = uuid4().hex[:8]
    session_ids = [f"pytest-batch-{token}-a", f"pytest-batch-{token}-b"]

    for session_id in session_ids:
        messages = [
            {
                "source": "pytest",
                "session_id": session_id,
                "role": "user",
                "content": f"想判断这条会话要不要先稍后处理。 {session_id}",
            },
            {
                "source": "pytest",
                "session_id": session_id,
                "role": "assistant",
                "content": f"建议后续统一清理 backlog。 {session_id}",
            },
        ]
        for message in messages:
            ingest = client.post("/api/ingest", json=message)
            assert ingest.status_code == 200

    refresh_resp = client.post("/api/inbox/refresh")
    assert refresh_resp.status_code == 200

    batch_later_resp = client.post(
        "/api/inbox/batch",
        json={
            "action": "later",
            "items": [{"source": "pytest", "session_id": session_id} for session_id in session_ids],
        },
    )
    inbox_after_later = client.get("/api/inbox", params={"include_ignored": "true", "q": token})

    assert batch_later_resp.status_code == 200
    assert batch_later_resp.json()["count"] == 2
    assert inbox_after_later.status_code == 200
    assert all(
        any(item["session_id"] == session_id and item["status"] == "later" for item in inbox_after_later.json()["groups"]["later"])
        for session_id in session_ids
    )

    batch_ready_resp = client.post(
        "/api/inbox/batch",
        json={
            "action": "ready",
            "items": [{"source": "pytest", "session_id": session_id} for session_id in session_ids],
        },
    )
    inbox_after_ready = client.get("/api/inbox", params={"include_ignored": "true", "q": token})

    assert batch_ready_resp.status_code == 200
    assert batch_ready_resp.json()["count"] == 2
    assert inbox_after_ready.status_code == 200
    assert all(
        any(item["session_id"] == session_id and item["status"] == "ready" for item in inbox_after_ready.json()["groups"]["ready"])
        for session_id in session_ids
    )


def test_inbox_batch_confirm_merges_tags_and_priority() -> None:
    token = uuid4().hex[:8]
    session_ids = [f"pytest-batch-confirm-{token}-a", f"pytest-batch-confirm-{token}-b"]

    for index, session_id in enumerate(session_ids):
        messages = [
            {
                "source": "pytest",
                "session_id": session_id,
                "role": "user",
                "content": f"这条会话需要统一确认建议。 {session_id}",
            },
            {
                "source": "pytest",
                "session_id": session_id,
                "role": "assistant",
                "content": f"建议整理成知识卡片。 {session_id}",
            },
        ]
        for message in messages:
            ingest = client.post("/api/ingest", json=message)
            assert ingest.status_code == 200
        if index == 0:
            single_confirm = client.post(
                "/api/inbox/confirm",
                json={
                    "source": "pytest",
                    "session_id": session_id,
                    "title": f"已有标签会话 {token}",
                    "tags": ["既有标签"],
                    "priority": "值得整理",
                },
            )
            assert single_confirm.status_code == 200

    refresh_resp = client.post("/api/inbox/refresh")
    assert refresh_resp.status_code == 200

    batch_confirm_resp = client.post(
        "/api/inbox/batch",
        json={
            "action": "confirm",
            "priority": "推荐优先整理",
            "tags": [f"共用{token}", "补偿"],
            "items": [{"source": "pytest", "session_id": session_id} for session_id in session_ids],
        },
    )
    inbox_resp = client.get("/api/inbox", params={"include_ignored": "true", "q": token})

    assert batch_confirm_resp.status_code == 200
    assert batch_confirm_resp.json()["count"] == 2
    assert inbox_resp.status_code == 200
    all_items = [item for items in inbox_resp.json()["groups"].values() for item in items]

    first_item = next(item for item in all_items if item["session_id"] == session_ids[0])
    second_item = next(item for item in all_items if item["session_id"] == session_ids[1])

    assert first_item["status"] == "ready"
    assert second_item["status"] == "ready"
    assert first_item["display_priority"] == "推荐优先整理"
    assert second_item["display_priority"] == "推荐优先整理"
    assert "既有标签" in first_item["display_tags"]
    assert f"共用{token}" in first_item["display_tags"]
    assert f"共用{token}" in second_item["display_tags"]


def test_inbox_batch_quick_save_creates_multiple_drafts() -> None:
    token = uuid4().hex[:8]
    session_ids = [f"pytest-batch-save-{token}-a", f"pytest-batch-save-{token}-b"]

    for session_id in session_ids:
        messages = [
            {
                "source": "pytest",
                "session_id": session_id,
                "role": "user",
                "content": f"这条会话适合直接批量存成草稿。 {session_id}",
            },
            {
                "source": "pytest",
                "session_id": session_id,
                "role": "assistant",
                "content": f"建议先快速沉淀成草稿，再后续统一完善。 {session_id}",
            },
        ]
        for message in messages:
            ingest = client.post("/api/ingest", json=message)
            assert ingest.status_code == 200

    refresh_resp = client.post("/api/inbox/refresh")
    assert refresh_resp.status_code == 200

    batch_save_resp = client.post(
        "/api/inbox/batch",
        json={
            "action": "quick_save",
            "items": [{"source": "pytest", "session_id": session_id} for session_id in session_ids],
        },
    )
    inbox_resp = client.get("/api/inbox", params={"q": token})

    assert batch_save_resp.status_code == 200
    assert batch_save_resp.json()["count"] == 2
    assert batch_save_resp.json()["reused_count"] == 0
    assert len(batch_save_resp.json()["notes"]) == 2
    assert all(note["status"] == "draft" for note in batch_save_resp.json()["notes"])
    assert all(note["source_count"] >= 2 for note in batch_save_resp.json()["notes"])
    assert inbox_resp.status_code == 200
    assert all(
        any(item["session_id"] == session_id and item["status"] == "done" for item in inbox_resp.json()["groups"]["done"])
        for session_id in session_ids
    )
