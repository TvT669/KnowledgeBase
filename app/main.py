from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import (
    CreateNoteRequest,
    IngestMessage,
    InboxConfirmRequest,
    InboxDeferRequest,
    InboxSessionRequest,
    NoteDraftRequest,
    QuickSessionNoteRequest,
    SearchQuery,
    SessionNoteDraftRequest,
    UpdateNoteRequest,
)
from app.services.ingest import insert_message
from app.services.inbox import (
    confirm_session_metadata,
    ensure_queue_entry,
    list_inbox_groups,
    mark_messages_done,
    mark_session_ignored,
    mark_session_later,
    mark_session_ready,
    reopen_sessions_for_deleted_note,
    refresh_inbox,
)
from app.services.notes import (
    create_note,
    delete_note,
    get_messages_by_ids,
    get_note,
    get_note_sources,
    latest_notes,
    search_notes,
    update_note,
)
from app.services.search import search_messages
from app.services.sessions import get_session_messages
from app.services.summarizer import generate_note_draft, summarize_text, title_needs_fallback

app = FastAPI(title="Local AI Knowledge Hub")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ingest")
async def ingest(payload: IngestMessage) -> dict[str, str | int]:
    summary = await summarize_text(payload.content)
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
    item = ensure_queue_entry(payload.source, payload.session_id)
    existing_note_id = item.get("note_id")
    if item.get("status") == "done" and existing_note_id:
        try:
            note = get_note(int(existing_note_id))
            return {"status": "ok", "note": note, "reused": True}
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
    note = create_note(
        title=draft["title"],
        problem=draft["problem"],
        root_cause=draft["root_cause"],
        solution=draft["solution"],
        key_takeaways=draft["key_takeaways"],
        message_ids=[int(message["id"]) for message in messages],
        status="draft",
        source_type="session",
    )
    mark_messages_done(messages, note_id=int(note["id"]))
    return {"status": "ok", "note": note, "reused": False}


@app.post("/api/notes")
def save_note(payload: CreateNoteRequest) -> dict[str, str | dict]:
    message_ids = list(dict.fromkeys(payload.message_ids))
    messages = get_messages_by_ids(message_ids)
    if len(messages) != len(message_ids):
        raise HTTPException(status_code=404, detail="message not found")

    note = create_note(
        title=payload.title,
        problem=payload.problem,
        root_cause=payload.root_cause,
        solution=payload.solution,
        key_takeaways=payload.key_takeaways,
        message_ids=message_ids,
        status=payload.status,
        source_type=payload.source_type,
    )
    mark_messages_done(messages, note_id=int(note["id"]))
    return {"status": "ok", "note": note}


@app.post("/api/notes/search")
def note_search(payload: SearchQuery) -> dict[str, list[dict]]:
    normalized = " ".join(payload.q.strip().split())
    if not normalized:
        return {"items": []}

    query = " OR ".join(normalized.split())
    return {"items": search_notes(query, payload.limit)}


@app.get("/api/notes/{note_id}/sources")
def note_sources(note_id: int) -> dict[str, list[dict]]:
    try:
        get_note(note_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="note not found")

    return {"items": get_note_sources(note_id)}


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
        context={"notes": notes},
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    refresh_inbox(limit=120)
    inbox_data = list_inbox_groups(limit_per_group=12)
    recent_notes = latest_notes(limit=4)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "inbox_groups": inbox_data["groups"],
            "inbox_stats": inbox_data["stats"],
            "recent_notes": recent_notes,
        },
    )
