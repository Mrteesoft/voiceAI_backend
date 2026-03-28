from __future__ import annotations

from app.services.chat_service import ChatService
from app.services.knowledge_service import KnowledgeService


def test_handle_message_persists_request_and_reply(db_session) -> None:
    KnowledgeService().seed_defaults(db_session)
    service = ChatService()

    response = service.handle_message(
        db=db_session,
        user_id="tester",
        message="Explain the backend architecture.",
    )

    assert response.session_id
    assert response.reply
    assert response.context_used
    assert response.retrieval_query
    assert response.citations
    assert [item.role for item in response.history] == ["user", "assistant"]


def test_existing_session_keeps_conversation_history(db_session) -> None:
    KnowledgeService().seed_defaults(db_session)
    service = ChatService()

    first = service.handle_message(
        db=db_session,
        user_id="tester",
        message="What handles streaming?",
    )
    second = service.handle_message(
        db=db_session,
        user_id="tester",
        session_id=first.session_id,
        message="What handles async jobs?",
    )

    assert second.session_id == first.session_id
    assert len(second.history) == 4
    assert second.history[-1].role == "assistant"
