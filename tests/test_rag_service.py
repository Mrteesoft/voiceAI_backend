from __future__ import annotations

from app.services.knowledge_service import KnowledgeService
from app.services.rag_service import RAGService


def test_prepare_generation_context_builds_grounded_rag_payload(db_session) -> None:
    knowledge_service = KnowledgeService()
    rag_service = RAGService()

    knowledge_service.create_document(
        db=db_session,
        title="rag-faq",
        content=(
            "RAG combines retrieval with generation. "
            "Relevant chunks should be cited so responses stay grounded."
        ),
    )

    result = rag_service.prepare_generation_context(
        db=db_session,
        user_message="How does RAG keep answers grounded?",
        history=[
            {"role": "user", "content": "Tell me about retrieval."},
            {"role": "assistant", "content": "What aspect?"},
            {"role": "user", "content": "How does RAG keep answers grounded?"},
        ],
    )

    assert result.retrieval_query
    assert "Tell me about retrieval." in result.retrieval_query
    assert result.context_items
    assert result.citations
    assert "rag-faq" in result.citations[0]
    assert "Retrieved sources:" in result.grounded_prompt
