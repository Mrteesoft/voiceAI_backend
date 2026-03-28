from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.models import KnowledgeChunk
from app.services.embeddings import EmbeddingService


class RetrievalService:
    def __init__(self) -> None:
        settings = get_settings()
        self.fallback_context = [
            "The assistant backend should expose REST APIs for chat, voice, and session management.",
            "A retrieval layer can add company knowledge or product documentation before model inference.",
            "Real-time systems often use WebSockets for token streaming and Redis queues for background jobs.",
        ]
        self.default_search_limit = settings.default_search_limit
        self.embedding_service = EmbeddingService()

    def get_context(self, db: Session, query: str, limit: int | None = None) -> list[str]:
        effective_limit = limit or self.default_search_limit
        results = self.search(db=db, query=query, limit=effective_limit)
        if results:
            return [item["content"] for item in results]

        return self.fallback_context[:effective_limit]

    def search(self, db: Session, query: str, limit: int = 5) -> list[dict[str, str | float | None]]:
        vector_results = self._vector_search(db=db, query=query, limit=limit)
        if vector_results:
            return vector_results

        return self._lexical_search(db=db, query=query, limit=limit)

    def _vector_search(
        self,
        db: Session,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, str | float | None]]:
        try:
            query_embedding = self.embedding_service.embed_text(query)
            distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
            statement = (
                select(KnowledgeChunk, distance.label("distance"))
                .options(selectinload(KnowledgeChunk.document))
                .where(KnowledgeChunk.embedding.is_not(None))
                .order_by(distance.asc(), KnowledgeChunk.chunk_index.asc())
                .limit(limit)
            )
            rows = db.execute(statement).all()
        except Exception:
            return []

        if not rows:
            return []

        return [
            {
                "content": chunk.content,
                "score": max(0.0, 1.0 - float(distance_value)),
                "document_title": chunk.document.title if chunk.document else None,
            }
            for chunk, distance_value in rows
        ]

    def _lexical_search(
        self,
        db: Session,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, str | float | None]]:
        query_terms = {term.lower() for term in query.split() if term.strip()}
        chunks = list(
            db.scalars(
                select(KnowledgeChunk)
                .options(selectinload(KnowledgeChunk.document))
                .order_by(
                    KnowledgeChunk.created_at.asc(),
                    KnowledgeChunk.chunk_index.asc(),
                )
            ).all()
        )
        if not chunks:
            return []

        scored_items: list[tuple[float, KnowledgeChunk]] = []
        for chunk in chunks:
            item_terms = {term.lower().strip(".,") for term in chunk.content.split()}
            lexical_overlap = len(query_terms.intersection(item_terms))
            phrase_bonus = 2 if query.lower() in chunk.content.lower() else 0
            density_bonus = lexical_overlap / max(len(item_terms), 1)
            score = float(lexical_overlap + phrase_bonus + density_bonus)
            scored_items.append((score, chunk))

        ranked = sorted(scored_items, key=lambda item: item[0], reverse=True)
        relevant = [
            {
                "content": chunk.content,
                "score": score,
                "document_title": chunk.document.title if chunk.document else None,
            }
            for score, chunk in ranked
            if score > 0
        ]

        if relevant:
            return relevant[:limit]

        return [
            {
                "content": chunk.content,
                "score": 0.0,
                "document_title": chunk.document.title if chunk.document else None,
            }
            for chunk in chunks[:limit]
        ]
