from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ChatMessage, ChatSession
from app.schemas.chat import ChatResponse, MessageResponse, SessionResponse
from app.services.interaction_pipeline import InteractionPipelineService


class ChatService:
    def __init__(self) -> None:
        settings = get_settings()
        self.pipeline_service = InteractionPipelineService()
        self.model_history_window_size = settings.model_history_window_size
        self.default_history_limit = settings.default_history_limit

    def handle_message(
        self,
        db: Session,
        user_id: str,
        message: str,
        session_id: str | None = None,
        channel: str = "text",
        platform: str = "web",
        audio_reference: str | None = None,
        audio_input: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ChatResponse:
        result = self.pipeline_service.process_interaction(
            db=db,
            user_id=user_id,
            message=message,
            session_id=session_id,
            channel=channel,
            platform=platform,
            audio_reference=audio_reference,
            audio_input=audio_input,
            metadata=metadata,
        )

        final_history = self._list_messages(
            db=db,
            session_id=result["session_id"],
            limit=self.default_history_limit,
        )
        return ChatResponse(
            session_id=result["session_id"],
            user_id=result["user_id"],
            reply=result["reply"],
            context_used=result["context_used"],
            platform=result["platform"],
            pipeline_run_id=result["run_id"],
            business_actions=result["business_actions"],
            voice_response=result["voice_response"],
            has_audio_input=result["has_audio_input"],
            history=[MessageResponse.model_validate(item) for item in final_history],
        )

    async def stream_message(
        self,
        db: Session,
        user_id: str,
        message: str,
        session_id: str | None = None,
        channel: str = "text",
        platform: str = "web",
        audio_reference: str | None = None,
        audio_input: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        async for event in self.pipeline_service.stream_interaction(
            db=db,
            user_id=user_id,
            message=message,
            session_id=session_id,
            channel=channel,
            platform=platform,
            audio_reference=audio_reference,
            audio_input=audio_input,
            metadata=metadata,
        ):
            yield event

    def get_session(
        self,
        db: Session,
        session_id: str,
        limit: int | None = None,
    ) -> SessionResponse | None:
        chat_session = db.get(ChatSession, session_id)
        if chat_session is None:
            return None

        history = self._list_messages(
            db=db,
            session_id=session_id,
            limit=limit or self.default_history_limit,
        )
        return SessionResponse(
            session_id=chat_session.id,
            user_id=chat_session.user_id,
            history=[MessageResponse.model_validate(item) for item in history],
        )

    def _list_messages(
        self,
        db: Session,
        session_id: str,
        limit: int | None = None,
    ) -> list[ChatMessage]:
        if limit is None:
            statement = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            )
            return list(db.scalars(statement).all())

        recent_statement = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
        )
        recent_messages = list(db.scalars(recent_statement).all())
        recent_messages.reverse()
        return recent_messages
