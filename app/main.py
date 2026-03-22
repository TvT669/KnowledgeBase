from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import IngestMessage, SearchQuery
from app.services.ingest import insert_message
from app.services.search import latest_messages, search_messages
from app.services.summarizer import summarize_text

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


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    items = latest_messages(limit=50)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"items": items},
    )
