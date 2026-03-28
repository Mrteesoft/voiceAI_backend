from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeDocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=20000)
    source_type: str = Field(default="manual", min_length=1, max_length=50)


class KnowledgeDocumentResponse(BaseModel):
    id: str
    title: str
    source_type: str
    chunk_count: int
    created_at: datetime


class RetrievalResultResponse(BaseModel):
    content: str
    score: float
    document_title: str | None


class RetrievalSearchResponse(BaseModel):
    query: str
    results: list[RetrievalResultResponse]
