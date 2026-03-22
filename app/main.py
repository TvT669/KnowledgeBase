from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import (
    CreateNoteRequest,
    IngestMessage,
    NoteDraftRequest,
    SearchQuery,
    SessionNoteDraftRequest,
    UpdateNoteRequest,
)
from app.services.ingest import insert_message
from app.services.notes import (
    create_note,
    get_messages_by_ids,
    get_note,
    get_note_sources,
    latest_notes,
    search_notes,
    update_note,
)
from app.services.search import latest_messages, search_messages
from app.services.sessions import get_session_messages, latest_sessions
from app.services.summarizer import generate_note_draft, summarize_text

app = FastAPI(title="Local AI Knowledge Hub")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


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


@app.post("/api/notes/generate")
async def generate_note(payload: NoteDraftRequest) -> dict[str, dict | list[dict]]:
    message_ids = list(dict.fromkeys(payload.message_ids))
    messages = get_messages_by_ids(message_ids)
    if len(messages) != len(message_ids):
        raise HTTPException(status_code=404, detail="message not found")

    draft = await generate_note_draft(messages)
    return {"draft": draft, "sources": messages}


@app.post("/api/notes/generate/session")
async def generate_session_note(payload: SessionNoteDraftRequest) -> dict[str, dict | list[dict]]:
    messages = get_session_messages(payload.source, payload.session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="session not found")

    draft = await generate_note_draft(messages)
    return {"draft": draft, "sources": messages}


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


@app.get("/notes", response_class=HTMLResponse)
def notes_page(request: Request) -> HTMLResponse:
    notes = latest_notes(limit=50)
    return templates.TemplateResponse(
        request=request,
        name="notes.html",
        context={"notes": notes},
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    items = latest_messages(limit=50)
    sessions = latest_sessions(limit=18)
    recent_notes = latest_notes(limit=4)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"items": items, "sessions": sessions, "recent_notes": recent_notes},
    )
