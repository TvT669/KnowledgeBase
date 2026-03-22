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


class MessageOut(BaseModel):
    id: int
    source: str
    session_id: str | None
    role: str
    content: str
    created_at: str
    summary: str | None
