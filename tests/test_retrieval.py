from __future__ import annotations

from app.services.knowledge_service import KnowledgeService
from app.services.retrieval import RetrievalService


def test_search_returns_ranked_persisted_chunks(db_session) -> None:
    knowledge_service = KnowledgeService()
    retrieval_service = RetrievalService()

    knowledge_service.create_document(
        db=db_session,
        title="faq",
        content=(
            "Vector databases support semantic retrieval for assistants. "
            "Hybrid search can combine SQL filters with similarity ranking."
        ),
    )

    results = retrieval_service.search(
        db=db_session,
        query="vector retrieval",
        limit=3,
    )

    assert results
    assert results[0]["document_title"] == "faq"
    assert "retrieval" in str(results[0]["content"]).lower()
