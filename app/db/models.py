from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.session import Base
from app.db.types import EmbeddingVectorType

settings = get_settings()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session_created_at", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_sessions.id"),
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class AsyncMessageJob(Base):
    __tablename__ = "async_message_jobs"
    __table_args__ = (
        Index("ix_async_message_jobs_status_created_at", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(20), default="text")
    platform: Mapped[str] = mapped_column(String(30), default="web", index=True)
    input_text: Mapped[str] = mapped_column(Text())
    audio_reference: Mapped[str | None] = mapped_column(Text(), nullable=True)
    request_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON(), default=dict)
    transcript: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    reply: Mapped[str | None] = mapped_column(Text(), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class InteractionRun(Base):
    __tablename__ = "interaction_runs"
    __table_args__ = (
        Index("ix_interaction_runs_session_created_at", "session_id", "created_at"),
        Index("ix_interaction_runs_channel_platform", "channel", "platform"),
        Index("ix_interaction_runs_status_created_at", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("chat_sessions.id"),
        nullable=True,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(20), default="text", index=True)
    platform: Mapped[str] = mapped_column(String(30), default="web", index=True)
    status: Mapped[str] = mapped_column(String(20), default="received", index=True)
    input_text: Mapped[str] = mapped_column(Text())
    normalized_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text(), nullable=True)
    audio_reference: Mapped[str | None] = mapped_column(Text(), nullable=True)
    reply: Mapped[str | None] = mapped_column(Text(), nullable=True)
    voice_response_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    request_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON(), default=dict)
    business_actions: Mapped[list[str]] = mapped_column(JSON(), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    events: Mapped[list["InteractionEvent"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class InteractionEvent(Base):
    __tablename__ = "interaction_events"
    __table_args__ = (
        Index("ix_interaction_events_run_created_at", "run_id", "created_at"),
        Index("ix_interaction_events_stage_created_at", "stage", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("interaction_runs.id"),
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(50), index=True)
    source: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict[str, str | int | float | bool | None | list[str]]] = mapped_column(
        JSON(),
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    run: Mapped[InteractionRun] = relationship(back_populates="events")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    title: Mapped[str] = mapped_column(String(200), index=True)
    source_type: Mapped[str] = mapped_column(String(50), default="manual")
    content: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index("ix_knowledge_chunks_document_chunk", "document_id", "chunk_index"),
        Index(
            "ix_knowledge_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_documents.id"),
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer())
    content: Mapped[str] = mapped_column(Text())
    embedding: Mapped[list[float] | None] = mapped_column(
        EmbeddingVectorType(settings.embedding_dimensions),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")
