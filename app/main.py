from __future__ import annotations

import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from urllib.parse import quote
from pathlib import Path

from app.models import (
    CreateNoteRequest,
    IngestBatchRequest,
    IngestMessage,
    InboxConfirmRequest,
    InboxDeferRequest,
    InboxBatchRequest,
    InboxSessionRequest,
    IdeSyncRequest,
    NoteBatchExportRequest,
    NoteDraftRequest,
    NoteRecommendationRequest,
    QuickAppendSessionNoteRequest,
    QuickSessionNoteRequest,
    SearchQuery,
    SessionNoteDraftRequest,
    UpdateNoteRequest,
)
from app.services.ingest import insert_message
from app.services.ide_sync import get_ide_sync_state, run_ide_sync, start_ide_sync
from app.services.inbox import (
    batch_confirm_session_metadata,
    confirm_session_metadata,
    ensure_queue_entry,
    list_inbox_groups,
    mark_messages_done,
    mark_session_ignored,
    mark_session_later,
    mark_session_ready,
    reopen_sessions_for_deleted_note,
    refresh_inbox,
    refresh_inbox_if_needed,
)
from app.services.notes import (
    append_to_note,
    create_note,
    delete_note,
    export_note_markdown,
    export_notes_markdown_zip,
    list_note_append_events,
    get_messages_by_ids,
    get_note,
    get_note_sources,
    latest_note_options,
    latest_notes,
    recommend_notes,
    search_notes,
    undo_note_append,
    update_note,
)
from app.services.search import search_messages
from app.services.sessions import get_session_messages
from app.services.summarizer import generate_note_draft, summarize_text, title_needs_fallback

app = FastAPI(title="Local AI Knowledge Hub")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
HOME_INBOX_LIMIT = 200


def _asset_version(*relative_paths: str) -> str:
    latest = 0
    root = Path(__file__).resolve().parent.parent
    for relative_path in relative_paths:
        try:
            latest = max(latest, int((root / relative_path).stat().st_mtime_ns))
        except OSError:
            continue
    return str(latest or 1)


def _apply_session_title_fallback(
    draft: dict[str, str],
    messages: list[dict],
    *,
    source: str | None = None,
    session_id: str | None = None,
) -> dict[str, str]:
    title = str(draft.get("title") or "").strip()
    if not title_needs_fallback(title):
        return draft

    resolved_source = source
    resolved_session_id = session_id
    if not resolved_source or not resolved_session_id:
        session_pairs = {
            (str(message.get("source")), str(message.get("session_id")))
            for message in messages
            if message.get("session_id")
        }
        if len(session_pairs) == 1:
            resolved_source, resolved_session_id = next(iter(session_pairs))

    if not resolved_source or not resolved_session_id:
        return draft

    try:
        item = ensure_queue_entry(resolved_source, resolved_session_id)
    except KeyError:
        return draft

    fallback_title = str(item.get("display_title") or "").strip()
    if fallback_title:
        draft["title"] = fallback_title[:120]
    return draft


def _require_ingest_token(request: Request) -> None:
    expected = os.getenv("KNOWLEDGE_API_TOKEN", "").strip()
    if not expected:
        return

    provided = request.headers.get("x-knowledge-token", "").strip()
    if not provided:
        auth_header = request.headers.get("authorization", "").strip()
        if auth_header.lower().startswith("bearer "):
            provided = auth_header[7:].strip()

    if provided != expected:
        raise HTTPException(status_code=401, detail="invalid api token")


async def _resolve_ingest_summary(payload: IngestMessage) -> str:
    provided_summary = str(payload.summary or "").strip()
    if provided_summary:
        return provided_summary
    return await summarize_text(payload.content)


async def _quick_save_session_note_internal(source: str, session_id: str) -> tuple[dict, bool]:
    item = ensure_queue_entry(source, session_id)
    existing_note_id = item.get("note_id")
    if item.get("status") == "done" and existing_note_id:
        try:
            note = get_note(int(existing_note_id))
            return note, True
        except KeyError:
            pass

    messages = get_session_messages(source, session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="session not found")

    draft = await generate_note_draft(messages)
    draft = _apply_session_title_fallback(
        draft,
        messages,
        source=source,
        session_id=session_id,
    )
    note = create_note(
        title=draft["title"],
        problem=draft["problem"],
        root_cause=draft["root_cause"],
        solution=draft["solution"],
        key_takeaways=draft["key_takeaways"],
        message_ids=[int(message["id"]) for message in messages],
        status="draft",
        source_type="session",
        tags=list(item.get("display_tags") or []),
    )
    mark_messages_done(messages, note_id=int(note["id"]))
    return note, False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ingest")
async def ingest(request: Request, payload: IngestMessage) -> dict[str, str | int]:
    _require_ingest_token(request)
    summary = await _resolve_ingest_summary(payload)
    inserted, row_id = insert_message(
        source=payload.source,
        session_id=payload.session_id,
        role=payload.role,
        content=payload.content,
        summary=summary,
    )
    if not inserted:
        raise HTTPException(status_code=409, detail="message already exists")

    return {"status": "ok", "id": row_id or 0}


@app.post("/api/ingest/batch")
async def ingest_batch(request: Request, payload: IngestBatchRequest) -> dict[str, int | str]:
    _require_ingest_token(request)

    inserted_count = 0
    deduped_count = 0
    for item in payload.items:
        summary = await _resolve_ingest_summary(item)
        inserted, _ = insert_message(
            source=item.source,
            session_id=item.session_id,
            role=item.role,
            content=item.content,
            summary=summary,
        )
        if inserted:
            inserted_count += 1
        else:
            deduped_count += 1

    return {
        "status": "ok",
        "received_count": len(payload.items),
        "inserted_count": inserted_count,
        "deduped_count": deduped_count,
    }


@app.post("/api/search")
def search(payload: SearchQuery) -> dict[str, list[dict]]:
    # FTS query supports operators; wrap plain text for better recall.
    normalized = " ".join(payload.q.strip().split())
    if not normalized:
        return {"items": []}

    query = " OR ".join(normalized.split())
    return {"items": search_messages(query, payload.limit)}


@app.get("/api/sessions/messages")
def session_messages(source: str, session_id: str) -> dict[str, list[dict]]:
    messages = get_session_messages(source, session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="session not found")

    return {"items": messages}


@app.post("/api/notes/generate")
async def generate_note(payload: NoteDraftRequest) -> dict[str, dict | list[dict]]:
    message_ids = list(dict.fromkeys(payload.message_ids))
    messages = get_messages_by_ids(message_ids)
    if len(messages) != len(message_ids):
        raise HTTPException(status_code=404, detail="message not found")

    draft = await generate_note_draft(messages)
    draft = _apply_session_title_fallback(draft, messages)
    return {"draft": draft, "sources": messages}


@app.post("/api/notes/generate/session")
async def generate_session_note(payload: SessionNoteDraftRequest) -> dict[str, dict | list[dict]]:
    messages = get_session_messages(payload.source, payload.session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="session not found")

    draft = await generate_note_draft(messages)
    draft = _apply_session_title_fallback(
        draft,
        messages,
        source=payload.source,
        session_id=payload.session_id,
    )
    return {"draft": draft, "sources": messages}


@app.post("/api/notes/quick-save/session")
async def quick_save_session_note(payload: QuickSessionNoteRequest) -> dict[str, str | bool | dict]:
    note, reused = await _quick_save_session_note_internal(payload.source, payload.session_id)
    return {"status": "ok", "note": note, "reused": reused}


@app.post("/api/notes/quick-append/session")
async def quick_append_session_note(payload: QuickAppendSessionNoteRequest) -> dict[str, str | bool | dict | None]:
    item = ensure_queue_entry(payload.source, payload.session_id)
    existing_note_id = item.get("note_id")
    if item.get("status") == "done" and existing_note_id and int(existing_note_id) == int(payload.note_id):
        try:
            note = get_note(int(existing_note_id))
            return {"status": "ok", "note": note, "reused": True, "append_summary": None}
        except KeyError:
            pass

    messages = get_session_messages(payload.source, payload.session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="session not found")

    draft = await generate_note_draft(messages)
    draft = _apply_session_title_fallback(
        draft,
        messages,
        source=payload.source,
        session_id=payload.session_id,
    )
    try:
        note, append_summary = append_to_note(
            payload.note_id,
            problem=draft["problem"],
            root_cause=draft["root_cause"],
            solution=draft["solution"],
            key_takeaways=draft["key_takeaways"],
            message_ids=[int(message["id"]) for message in messages],
            messages=messages,
            source_type="session",
            tags=list(item.get("display_tags") or []),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="note not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    mark_messages_done(messages, note_id=int(note["id"]))
    return {"status": "ok", "note": note, "reused": False, "append_summary": append_summary}


@app.post("/api/notes")
def save_note(payload: CreateNoteRequest) -> dict[str, str | dict | None]:
    message_ids = list(dict.fromkeys(payload.message_ids))
    messages = get_messages_by_ids(message_ids)
    if len(messages) != len(message_ids):
        raise HTTPException(status_code=404, detail="message not found")

    try:
        if payload.existing_note_id:
            note, append_summary = append_to_note(
                payload.existing_note_id,
                problem=payload.problem,
                root_cause=payload.root_cause,
                solution=payload.solution,
                key_takeaways=payload.key_takeaways,
                message_ids=message_ids,
                messages=messages,
                source_type=payload.source_type,
                tags=payload.tags,
            )
        else:
            note = create_note(
                title=payload.title,
                problem=payload.problem,
                root_cause=payload.root_cause,
                solution=payload.solution,
                key_takeaways=payload.key_takeaways,
                message_ids=message_ids,
                status=payload.status,
                source_type=payload.source_type,
                tags=payload.tags,
            )
            append_summary = None
    except KeyError:
        raise HTTPException(status_code=404, detail="note not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    mark_messages_done(messages, note_id=int(note["id"]))
    return {"status": "ok", "note": note, "append_summary": append_summary}


@app.post("/api/notes/search")
def note_search(payload: SearchQuery) -> dict[str, list[dict]]:
    normalized = " ".join(payload.q.strip().split())
    if not normalized:
        return {"items": []}

    query = " OR ".join(normalized.split())
    return {"items": search_notes(query, payload.limit)}


@app.post("/api/notes/recommend")
def note_recommend(payload: NoteRecommendationRequest) -> dict[str, list[dict]]:
    return {
        "items": recommend_notes(
            title=payload.title,
            problem=payload.problem,
            root_cause=payload.root_cause,
            solution=payload.solution,
            key_takeaways=payload.key_takeaways,
            tags=payload.tags,
            limit=payload.limit,
        )
    }


@app.get("/api/notes/{note_id}/sources")
def note_sources(note_id: int) -> dict[str, list[dict]]:
    try:
        get_note(note_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="note not found")

    return {"items": get_note_sources(note_id)}


@app.get("/api/notes/{note_id}/history")
def note_history(note_id: int) -> dict[str, list[dict]]:
    try:
        get_note(note_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="note not found")

    return {"items": list_note_append_events(note_id)}


@app.get("/api/notes/{note_id}/export.md")
def export_note_markdown_api(note_id: int) -> Response:
    try:
        markdown, filename = export_note_markdown(note_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="note not found")

    ascii_fallback = f"note-{note_id}.md"
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_fallback}"; '
                f"filename*=UTF-8''{quote(filename)}"
            )
        },
    )


@app.post("/api/notes/export.zip")
def export_notes_markdown_zip_api(payload: NoteBatchExportRequest) -> Response:
    try:
        archive_bytes, filename = export_notes_markdown_zip(payload.note_ids)
    except KeyError:
        raise HTTPException(status_code=404, detail="note not found")

    return Response(
        content=archive_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/notes/{note_id}/history/{event_id}/undo")
def undo_note_history_event(note_id: int, event_id: int) -> dict[str, str | dict | list[dict]]:
    try:
        note, undone_event, reopen_pairs = undo_note_append(note_id, event_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="note or append event not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    if reopen_pairs:
        reopen_sessions_for_deleted_note(note_id, reopen_pairs)

    return {
        "status": "ok",
        "note": note,
        "undone_event": undone_event,
        "history": list_note_append_events(note_id),
    }


@app.put("/api/notes/{note_id}")
def edit_note(note_id: int, payload: UpdateNoteRequest) -> dict[str, str | dict]:
    try:
        note = update_note(
            note_id,
            title=payload.title,
            problem=payload.problem,
            root_cause=payload.root_cause,
            solution=payload.solution,
            key_takeaways=payload.key_takeaways,
            status=payload.status,
            source_type=payload.source_type,
            tags=payload.tags,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="note not found")

    return {"status": "ok", "note": note}


@app.delete("/api/notes/{note_id}")
def remove_note(note_id: int) -> dict[str, str]:
    try:
        session_pairs = delete_note(note_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="note not found")

    reopen_sessions_for_deleted_note(note_id, session_pairs)
    return {"status": "ok"}


@app.get("/api/inbox")
def inbox(
    limit_per_group: int = 12,
    include_ignored: bool = False,
    q: str = "",
) -> dict[str, dict | list]:
    return list_inbox_groups(limit_per_group=limit_per_group, include_ignored=include_ignored, query=q)


@app.post("/api/inbox/refresh")
def refresh_inbox_api() -> dict[str, str | dict]:
    stats = refresh_inbox(limit=120)
    return {"status": "ok", "refresh": stats}


@app.get("/api/sync/ide/status")
def ide_sync_status() -> dict[str, dict]:
    return {"state": get_ide_sync_state()}


@app.post("/api/sync/ide")
async def ide_sync_api(payload: IdeSyncRequest) -> dict[str, str | dict]:
    if not payload.wait:
        try:
            state = start_ide_sync(
                include_vscode=payload.include_vscode,
                include_windsurf=payload.include_windsurf,
                use_llm_summary=False,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        return JSONResponse(
            status_code=202,
            content={
                "status": "started",
                "state": state,
            },
        )

    try:
        sync_stats = await run_ide_sync(
            include_vscode=payload.include_vscode,
            include_windsurf=payload.include_windsurf,
            use_llm_summary=False,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    refresh_stats = refresh_inbox(limit=120)
    return {
        "status": "ok",
        "sync": sync_stats,
        "refresh": refresh_stats,
        "state": get_ide_sync_state(),
    }


@app.post("/api/inbox/confirm")
def confirm_inbox_session(payload: InboxConfirmRequest) -> dict[str, dict]:
    item = confirm_session_metadata(
        payload.source,
        payload.session_id,
        title=payload.title,
        tags=payload.tags,
        priority=payload.priority,
    )
    return {"item": item}


@app.post("/api/inbox/defer")
def defer_inbox_session(payload: InboxDeferRequest) -> dict[str, dict]:
    item = mark_session_later(payload.source, payload.session_id, snooze_until=payload.snooze_until)
    return {"item": item}


@app.post("/api/inbox/ignore")
def ignore_inbox_session(payload: InboxSessionRequest) -> dict[str, dict]:
    item = mark_session_ignored(payload.source, payload.session_id)
    return {"item": item}


@app.post("/api/inbox/ready")
def ready_inbox_session(payload: InboxSessionRequest) -> dict[str, dict]:
    item = mark_session_ready(payload.source, payload.session_id)
    return {"item": item}


@app.post("/api/inbox/batch")
async def inbox_batch_action(payload: InboxBatchRequest) -> dict[str, int | list[dict] | None]:
    action = payload.action.strip().lower()
    if action not in {"ready", "later", "ignored", "confirm", "quick_save"}:
        raise HTTPException(status_code=400, detail="unsupported batch action")
    if action == "confirm" and not str(payload.priority or "").strip():
        raise HTTPException(status_code=400, detail="priority is required for batch confirm")

    updated: list[dict] = []
    notes: list[dict] = []
    reused_count = 0
    for item in payload.items:
        if action == "ready":
            updated.append(mark_session_ready(item.source, item.session_id))
        elif action == "later":
            updated.append(mark_session_later(item.source, item.session_id, snooze_until=payload.snooze_until))
        elif action == "confirm":
            updated.append(
                batch_confirm_session_metadata(
                    item.source,
                    item.session_id,
                    tags=payload.tags,
                    priority=payload.priority,
                )
            )
        elif action == "quick_save":
            note, reused = await _quick_save_session_note_internal(item.source, item.session_id)
            notes.append(note)
            if reused:
                reused_count += 1
        else:
            updated.append(mark_session_ignored(item.source, item.session_id))

    return {
        "count": len(notes) if action == "quick_save" else len(updated),
        "items": updated if action != "quick_save" else [],
        "notes": notes if action == "quick_save" else [],
        "reused_count": reused_count if action == "quick_save" else None,
    }


@app.get("/notes", response_class=HTMLResponse)
def notes_page(request: Request) -> HTMLResponse:
    notes = latest_notes(limit=50)
    focus_note_id = request.query_params.get("note_id")
    if focus_note_id:
        try:
            focus_note = get_note(int(focus_note_id))
        except (KeyError, ValueError):
            focus_note = None
        if focus_note and all(int(note["id"]) != int(focus_note["id"]) for note in notes):
            notes.insert(0, focus_note)
    return templates.TemplateResponse(
        request=request,
        name="notes.html",
        context={
            "notes": notes,
            "asset_version": _asset_version("static/style.css", "static/notes.js"),
        },
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    refresh_state = refresh_inbox_if_needed(limit=120, max_age_seconds=300)
    inbox_data = list_inbox_groups(limit_per_group=HOME_INBOX_LIMIT)
    inbox_stats = dict(inbox_data["stats"])
    inbox_stats["pending_count"] = len(inbox_data["groups"].get("ready", [])) + len(inbox_data["groups"].get("new", []))
    inbox_stats["ready_count"] = len(inbox_data["groups"].get("ready", []))
    recent_notes = latest_notes(limit=4, exclude_status="draft")
    draft_notes = latest_notes(limit=4, status="draft")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "inbox_groups": inbox_data["groups"],
            "inbox_stats": inbox_stats,
            "inbox_refresh_state": refresh_state["state"],
            "sync_state": get_ide_sync_state(),
            "recent_notes": recent_notes,
            "draft_notes": draft_notes,
            "note_options": latest_note_options(limit=50),
            "asset_version": _asset_version("static/style.css", "static/home.js"),
        },
    )
