from __future__ import annotations

from pydantic import BaseModel, Field


class IngestMessage(BaseModel):
    source: str = Field(..., description="来源，例如 vscode、terminal")
    session_id: str | None = Field(default=None, description="会话ID")
    role: str = Field(..., description="user/assistant/system")
    content: str = Field(..., min_length=1, description="消息内容")
    summary: str | None = Field(default=None, description="可选的预计算摘要")


class IngestBatchRequest(BaseModel):
    items: list[IngestMessage] = Field(..., min_length=1, max_length=500)


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


class QuickAppendSessionNoteRequest(QuickSessionNoteRequest):
    note_id: int = Field(..., ge=1)


class NoteRecommendationRequest(BaseModel):
    title: str = Field(default="", max_length=120)
    problem: str = Field(default="")
    root_cause: str = Field(default="")
    solution: str = Field(default="")
    key_takeaways: str = Field(default="")
    tags: list[str] = Field(default_factory=list, max_length=12)
    limit: int = Field(default=5, ge=1, le=10)


class CreateNoteRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    problem: str = Field(..., min_length=1)
    root_cause: str = Field(..., min_length=1)
    solution: str = Field(..., min_length=1)
    key_takeaways: str = Field(..., min_length=1)
    message_ids: list[int] = Field(..., min_length=1, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=12)
    existing_note_id: int | None = Field(default=None, ge=1)
    status: str = Field(default="draft")
    source_type: str = Field(default="mixed")


class UpdateNoteRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    problem: str = Field(..., min_length=1)
    root_cause: str = Field(..., min_length=1)
    solution: str = Field(..., min_length=1)
    key_takeaways: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list, max_length=12)
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


class InboxBatchItem(BaseModel):
    source: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)


class InboxBatchRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=20)
    items: list[InboxBatchItem] = Field(..., min_length=1, max_length=100)
    snooze_until: str | None = Field(default=None)
    tags: list[str] = Field(default_factory=list, max_length=12)
    priority: str | None = Field(default=None, max_length=40)


class IdeSyncRequest(BaseModel):
    include_vscode: bool = Field(default=True)
    include_windsurf: bool = Field(default=True)
    wait: bool = Field(default=False)


class NoteBatchExportRequest(BaseModel):
    note_ids: list[int] = Field(..., min_length=1, max_length=100)


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
    status_label: str
    source_type: str
    created_at: str
    updated_at: str
    source_count: int
    source_labels: list[str]
    tags: list[str]
    stack_tags: list[str]
