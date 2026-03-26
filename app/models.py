from __future__ import annotations

from pydantic import BaseModel, Field


class IngestMessage(BaseModel):
    source: str = Field(..., description="来源，例如 vscode、terminal")
    session_id: str | None = Field(default=None, description="会话ID")
    role: str = Field(..., description="user/assistant/system")
    content: str = Field(..., min_length=1, description="消息内容")


class SearchQuery(BaseModel):
    q: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=100)


class NoteDraftRequest(BaseModel):
    message_ids: list[int] = Field(..., min_length=1, max_length=200)


class SessionNoteDraftRequest(BaseModel):
    source: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)


class QuickSessionNoteRequest(BaseModel):
    source: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)


class CreateNoteRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    problem: str = Field(..., min_length=1)
    root_cause: str = Field(..., min_length=1)
    solution: str = Field(..., min_length=1)
    key_takeaways: str = Field(..., min_length=1)
    message_ids: list[int] = Field(..., min_length=1, max_length=200)
    status: str = Field(default="draft")
    source_type: str = Field(default="mixed")


class UpdateNoteRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    problem: str = Field(..., min_length=1)
    root_cause: str = Field(..., min_length=1)
    solution: str = Field(..., min_length=1)
    key_takeaways: str = Field(..., min_length=1)
    status: str = Field(default="draft")
    source_type: str = Field(default="mixed")


class InboxSessionRequest(BaseModel):
    source: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)


class InboxConfirmRequest(InboxSessionRequest):
    title: str = Field(default="", max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=12)
    priority: str = Field(default="值得整理", max_length=40)


class InboxDeferRequest(InboxSessionRequest):
    snooze_until: str | None = Field(default=None)


class MessageOut(BaseModel):
    id: int
    source: str
    session_id: str | None
    role: str
    content: str
    created_at: str
    summary: str | None


class NoteOut(BaseModel):
    id: int
    title: str
    problem: str
    root_cause: str
    solution: str
    key_takeaways: str
    status: str
    source_type: str
    created_at: str
    updated_at: str
    source_count: int
    source_labels: list[str]
