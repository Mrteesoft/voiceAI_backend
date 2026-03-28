from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.models import KnowledgeChunk, KnowledgeDocument
from app.services.embeddings import EmbeddingService

logger = logging.getLogger("app.knowledge")


class KnowledgeService:
    def __init__(self) -> None:
        settings = get_settings()
        self.default_document_limit = settings.default_document_limit
        self.embedding_service = EmbeddingService()
        self.seed_documents = [
            {
                "title": "assistant-architecture",
                "source_type": "seed",
                "content": (
                    "The backend should expose APIs for chat, voice, authentication, session "
                    "management, and analytics. A request should pass through validation, "
                    "retrieval, model inference, persistence, and observability layers."
                ),
            },
            {
                "title": "realtime-and-async",
                "source_type": "seed",
                "content": (
                    "Real-time communication commonly uses WebSockets for token streaming. "
                    "Asynchronous workloads such as voice transcription, summarization, and "
                    "notifications are usually handled by queues and background workers."
                ),
            },
            {
                "title": "retrieval-patterns",
                "source_type": "seed",
                "content": (
                    "Retrieval systems often combine SQL metadata storage with vector search or "
                    "hybrid search. Documents are chunked, indexed, and ranked before the best "
                    "context is attached to the model prompt."
                ),
            },
        ]

    def seed_defaults(self, db: Session) -> None:
        existing_count = db.scalar(select(func.count()).select_from(KnowledgeDocument))
        if existing_count and existing_count > 0:
            return

        for item in self.seed_documents:
            self.create_document(
                db=db,
                title=item["title"],
                content=item["content"],
                source_type=item["source_type"],
                commit=False,
            )

        db.commit()

    def create_document(
        self,
        db: Session,
        title: str,
        content: str,
        source_type: str = "manual",
        commit: bool = True,
    ) -> KnowledgeDocument:
        document = KnowledgeDocument(
            title=title,
            source_type=source_type,
            content=content,
        )
        db.add(document)
        db.flush()

        chunk_models: list[KnowledgeChunk] = []
        for index, chunk in enumerate(self._chunk_text(content)):
            chunk_model = KnowledgeChunk(
                document_id=document.id,
                chunk_index=index,
                content=chunk,
                embedding=self.embedding_service.embed_text(chunk),
            )
            db.add(chunk_model)
            chunk_models.append(chunk_model)

        db.flush()

        if commit:
            db.commit()
            db.refresh(document)

        return document

    def list_documents(self, db: Session) -> list[KnowledgeDocument]:
        return self.list_documents_limited(db=db, limit=self.default_document_limit)

    def list_documents_limited(self, db: Session, limit: int) -> list[KnowledgeDocument]:
        statement = (
            select(KnowledgeDocument)
            .options(selectinload(KnowledgeDocument.chunks))
            .order_by(KnowledgeDocument.created_at.desc())
            .limit(limit)
        )
        return list(db.scalars(statement).all())

    def backfill_missing_embeddings(self, db: Session) -> int:
        statement = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.embedding.is_(None))
            .order_by(KnowledgeChunk.created_at.asc(), KnowledgeChunk.chunk_index.asc())
        )
        chunks = list(db.scalars(statement).all())
        if not chunks:
            return 0

        for chunk in chunks:
            chunk.embedding = self.embedding_service.embed_text(chunk.content)

        db.commit()
        logger.info("pgvector_embedding_backfill_completed count=%s", len(chunks))
        return len(chunks)

    def _chunk_text(self, content: str, chunk_size: int = 40) -> list[str]:
        words = content.split()
        if not words:
            return [content]

        return [
            " ".join(words[index : index + chunk_size])
            for index in range(0, len(words), chunk_size)
        ]
