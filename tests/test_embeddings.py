from __future__ import annotations

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import KnowledgeChunk
from app.services.embeddings import EmbeddingService
from app.services.knowledge_service import KnowledgeService


def test_embedding_service_returns_fixed_dimension_vectors() -> None:
    settings = get_settings()
    vector = EmbeddingService().embed_text("semantic retrieval in postgres")

    assert len(vector) == settings.embedding_dimensions
    assert any(value != 0.0 for value in vector)


def test_create_document_persists_chunk_embeddings(db_session) -> None:
    settings = get_settings()
    service = KnowledgeService()

    document = service.create_document(
        db=db_session,
        title="pgvector-notes",
        content=(
            "PostgreSQL can store embeddings with pgvector. "
            "Chunks should keep their vector values in the database."
        ),
    )

    chunks = list(
        db_session.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document.id)
            .order_by(KnowledgeChunk.chunk_index.asc())
        ).all()
    )

    assert chunks
    assert all(chunk.embedding is not None for chunk in chunks)
    assert all(len(chunk.embedding) == settings.embedding_dimensions for chunk in chunks)
