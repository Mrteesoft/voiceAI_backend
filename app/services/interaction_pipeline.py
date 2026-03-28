from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    ChatMessage,
    ChatSession,
    InteractionEvent,
    InteractionRun,
)
from app.services.business_logic_service import BusinessLogicService
from app.services.model_client import get_model_client
from app.services.rag_service import RAGService
from app.services.voice_service import VoiceService


class InteractionPipelineService:
    def __init__(self) -> None:
        settings = get_settings()
        self.model_history_window_size = settings.model_history_window_size
        self.rag_service = RAGService()
        self.model_client = get_model_client()
        self.voice_service = VoiceService()
        self.business_logic_service = BusinessLogicService()

    def process_interaction(
        self,
        *,
        db: Session,
        user_id: str,
        message: str,
        session_id: str | None = None,
        channel: str = "text",
        platform: str = "web",
        audio_reference: str | None = None,
        audio_input: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        prepared = self._prepare_interaction(
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

        reply = self.model_client.generate_reply(
            user_message=prepared["normalized_text"],
            history=prepared["history"],
            context=prepared["context"],
            channel=channel,
            platform=platform,
            business_actions=prepared["business_actions"],
            retrieval_query=prepared["retrieval_query"],
            citations=prepared["citations"],
            rag_prompt=prepared["rag_prompt"],
        )
        self._record_event(
            db=db,
            run=prepared["run"],
            stage="model_completed",
            source="model",
            payload={"reply_length": len(reply)},
        )

        voice_response = self.voice_service.build_voice_response(
            channel=channel,
            platform=platform,
            reply=reply,
            preferred_format=prepared["audio_format"],
        )
        if voice_response is not None:
            self._record_event(
                db=db,
                run=prepared["run"],
                stage="voice_response_ready",
                source="voice",
                payload=voice_response,
            )

        return self._finalize_interaction(
            db=db,
            run=prepared["run"],
            chat_session=prepared["chat_session"],
            normalized_text=prepared["normalized_text"],
            reply=reply,
            context=prepared["context"],
            retrieval_query=prepared["retrieval_query"],
            citations=prepared["citations"],
            channel=channel,
            platform=platform,
            metadata=prepared["metadata"],
            business_actions=prepared["business_actions"],
            voice_response=voice_response,
        )

    async def stream_interaction(
        self,
        *,
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
        prepared = self._prepare_interaction(
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

        yield {
            "event": "session_ready",
            "session_id": prepared["chat_session"].id,
            "channel": channel,
            "platform": platform,
            "run_id": prepared["run"].id,
        }
        yield {
            "event": "input_normalized",
            "run_id": prepared["run"].id,
            "normalized_text": prepared["normalized_text"],
            "transcript": prepared["transcript"],
        }
        yield {
            "event": "context_loaded",
            "run_id": prepared["run"].id,
            "items": prepared["context"],
        }
        yield {
            "event": "rag_prepared",
            "run_id": prepared["run"].id,
            "retrieval_query": prepared["retrieval_query"],
            "citations": prepared["citations"],
        }
        yield {
            "event": "business_logic_applied",
            "run_id": prepared["run"].id,
            "actions": prepared["business_actions"],
            "integration_targets": prepared["integration_targets"],
        }

        reply_parts: list[str] = []
        async for token in self.model_client.stream_reply(
            user_message=prepared["normalized_text"],
            history=prepared["history"],
            context=prepared["context"],
            channel=channel,
            platform=platform,
            business_actions=prepared["business_actions"],
            retrieval_query=prepared["retrieval_query"],
            citations=prepared["citations"],
            rag_prompt=prepared["rag_prompt"],
        ):
            reply_parts.append(token)
            yield {
                "event": "token",
                "run_id": prepared["run"].id,
                "token": token,
            }

        reply = "".join(reply_parts).strip()
        self._record_event(
            db=db,
            run=prepared["run"],
            stage="model_completed",
            source="model",
            payload={"reply_length": len(reply)},
        )

        voice_response = self.voice_service.build_voice_response(
            channel=channel,
            platform=platform,
            reply=reply,
            preferred_format=prepared["audio_format"],
        )
        if voice_response is not None:
            self._record_event(
                db=db,
                run=prepared["run"],
                stage="voice_response_ready",
                source="voice",
                payload=voice_response,
            )
            yield {
                "event": "voice_response_ready",
                "run_id": prepared["run"].id,
                "voice_response": voice_response,
            }

        result = self._finalize_interaction(
            db=db,
            run=prepared["run"],
            chat_session=prepared["chat_session"],
            normalized_text=prepared["normalized_text"],
            reply=reply,
            context=prepared["context"],
            retrieval_query=prepared["retrieval_query"],
            citations=prepared["citations"],
            channel=channel,
            platform=platform,
            metadata=prepared["metadata"],
            business_actions=prepared["business_actions"],
            voice_response=voice_response,
        )
        yield {
            "event": "complete",
            "run_id": result["run_id"],
            "session_id": result["session_id"],
            "reply": result["reply"],
            "history_length": result["history_length"],
            "platform": result["platform"],
        }

    def get_run(self, db: Session, run_id: str) -> InteractionRun | None:
        return db.get(InteractionRun, run_id)

    def get_run_response(self, db: Session, run_id: str) -> dict[str, Any] | None:
        run = self.get_run(db=db, run_id=run_id)
        if run is None:
            return None

        events = self._list_run_events(db=db, run_id=run.id)
        context_event = next((event for event in events if event.stage == "context_loaded"), None)
        rag_event = next((event for event in events if event.stage == "rag_prepared"), None)
        voice_event = next((event for event in events if event.stage == "voice_response_ready"), None)
        return {
            "run_id": run.id,
            "session_id": run.session_id or "",
            "user_id": run.user_id,
            "channel": run.channel,
            "platform": run.platform,
            "status": run.status,
            "input_text": run.input_text,
            "normalized_text": run.normalized_text or run.input_text,
            "transcript": run.transcript,
            "reply": run.reply or "",
            "context_used": list(context_event.payload.get("items", [])) if context_event else [],
            "retrieval_query": str(rag_event.payload.get("retrieval_query", run.input_text)) if rag_event else run.input_text,
            "citations": list(rag_event.payload.get("citations", [])) if rag_event else [],
            "business_actions": list(run.business_actions or []),
            "metadata": self._sanitize_metadata(run.request_metadata or {}),
            "voice_response": voice_event.payload if voice_event else None,
            "has_audio_input": self._extract_audio_input(run.request_metadata or {}) is not None,
            "events": [self._event_to_payload(event) for event in events],
            "audio_reference": run.audio_reference,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
        }

    def _prepare_interaction(
        self,
        *,
        db: Session,
        user_id: str,
        message: str,
        session_id: str | None,
        channel: str,
        platform: str,
        audio_reference: str | None,
        audio_input: dict[str, object] | None,
        metadata: dict[str, object] | None,
    ) -> dict[str, Any]:
        normalized_metadata = dict(metadata or {})
        if audio_input is not None:
            normalized_metadata["audio_input"] = audio_input

        chat_session = self._get_or_create_session(
            db=db,
            user_id=user_id,
            session_id=session_id,
        )
        run = InteractionRun(
            user_id=user_id,
            session_id=chat_session.id,
            channel=channel,
            platform=platform,
            status="received",
            input_text=message,
            audio_reference=audio_reference,
            request_metadata=normalized_metadata,
        )
        db.add(run)
        db.flush()

        self._record_event(
            db=db,
            run=run,
            stage="input_received",
            source="api",
            payload={
                "channel": channel,
                "platform": platform,
                "has_audio_reference": bool(audio_reference),
                "has_audio_input": audio_input is not None,
            },
        )

        normalized_input = self.voice_service.normalize_input(
            channel=channel,
            message=message,
            platform=platform,
            audio_reference=audio_reference,
            audio_input=audio_input,
            metadata=normalized_metadata,
        )
        normalized_text = str(normalized_input["normalized_text"] or message).strip()
        transcript = normalized_input["transcript"]
        audio_format = self._safe_string(normalized_input.get("audio_format"))
        run.normalized_text = normalized_text
        run.transcript = str(transcript) if transcript else None
        run.status = "normalized"
        db.add(
            ChatMessage(
                session_id=chat_session.id,
                role="user",
                content=normalized_text,
            )
        )
        db.flush()

        self._record_event(
            db=db,
            run=run,
            stage="input_normalized",
            source="voice",
            payload={
                "normalized_text": normalized_text,
                "transcript": run.transcript,
                "input_transport": str(normalized_input["input_transport"]),
                "audio_format": audio_format,
                "audio_size_bytes": normalized_input.get("audio_size_bytes"),
            },
        )

        history_records = self._list_messages(
            db=db,
            session_id=chat_session.id,
            limit=self.model_history_window_size,
        )
        history = [
            {"role": record.role, "content": record.content}
            for record in history_records
        ]

        rag_result = self.rag_service.prepare_generation_context(
            db=db,
            user_message=normalized_text,
            history=history,
        )
        context = rag_result.context_texts
        self._record_event(
            db=db,
            run=run,
            stage="context_loaded",
            source="retrieval",
            payload={"items": context},
        )
        self._record_event(
            db=db,
            run=run,
            stage="rag_prepared",
            source="rag",
            payload={
                "retrieval_query": rag_result.retrieval_query,
                "citations": rag_result.citations,
                "sources": [
                    {
                        "chunk_id": item.chunk_id,
                        "citation": item.citation,
                        "document_title": item.document_title,
                        "score": item.score,
                        "retrieval_strategy": item.retrieval_strategy,
                    }
                    for item in rag_result.context_items
                ],
            },
        )

        business_outcome = self.business_logic_service.evaluate(
            message=normalized_text,
            channel=channel,
            platform=platform,
            metadata=normalized_metadata,
        )
        business_actions = business_outcome["actions"]
        run.business_actions = business_actions
        run.status = "orchestrating"
        self._record_event(
            db=db,
            run=run,
            stage="business_logic_applied",
            source="business",
            payload=business_outcome,
        )
        db.flush()

        return {
            "chat_session": chat_session,
            "run": run,
            "normalized_text": normalized_text,
            "transcript": run.transcript,
            "history": history,
            "context": context,
            "rag_prompt": rag_result.grounded_prompt,
            "retrieval_query": rag_result.retrieval_query,
            "citations": rag_result.citations,
            "metadata": self._sanitize_metadata(normalized_metadata),
            "business_actions": business_actions,
            "integration_targets": business_outcome["integration_targets"],
            "audio_format": audio_format,
        }

    def _finalize_interaction(
        self,
        *,
        db: Session,
        run: InteractionRun,
        chat_session: ChatSession,
        normalized_text: str,
        reply: str,
        context: list[str],
        retrieval_query: str,
        citations: list[str],
        channel: str,
        platform: str,
        metadata: dict[str, object],
        business_actions: list[str],
        voice_response: dict[str, object] | None,
    ) -> dict[str, Any]:
        db.add(
            ChatMessage(
                session_id=chat_session.id,
                role="assistant",
                content=reply,
            )
        )
        run.reply = reply
        run.status = "completed"
        run.voice_response_text = voice_response["voice_prompt"] if voice_response else None
        self._record_event(
            db=db,
            run=run,
            stage="response_ready",
            source="pipeline",
            payload={"channel": channel, "platform": platform},
        )
        db.commit()

        history_length = len(self._list_messages(db=db, session_id=chat_session.id))
        return {
            "run_id": run.id,
            "session_id": chat_session.id,
            "user_id": chat_session.user_id,
            "channel": channel,
            "platform": platform,
            "status": run.status,
            "input_text": run.input_text,
            "normalized_text": normalized_text,
            "transcript": run.transcript,
            "reply": reply,
            "context_used": context,
            "retrieval_query": retrieval_query,
            "citations": citations,
            "business_actions": business_actions,
            "metadata": metadata,
            "voice_response": voice_response,
            "has_audio_input": self._extract_audio_input(run.request_metadata or {}) is not None,
            "history_length": history_length,
            "events": [
                self._event_to_payload(event)
                for event in self._list_run_events(db=db, run_id=run.id)
            ],
        }

    def _record_event(
        self,
        *,
        db: Session,
        run: InteractionRun,
        stage: str,
        source: str,
        payload: dict[str, Any],
    ) -> InteractionEvent:
        event = InteractionEvent(
            run_id=run.id,
            stage=stage,
            source=source,
            payload=payload,
        )
        db.add(event)
        db.flush()
        return event

    def _get_or_create_session(
        self,
        *,
        db: Session,
        user_id: str,
        session_id: str | None,
    ) -> ChatSession:
        if session_id:
            existing_session = db.get(ChatSession, session_id)
            if existing_session is not None:
                return existing_session

        new_session = ChatSession(user_id=user_id)
        db.add(new_session)
        db.flush()
        return new_session

    def _list_messages(
        self,
        *,
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

    def _list_run_events(self, *, db: Session, run_id: str) -> list[InteractionEvent]:
        statement = (
            select(InteractionEvent)
            .where(InteractionEvent.run_id == run_id)
            .order_by(InteractionEvent.created_at.asc(), InteractionEvent.id.asc())
        )
        return list(db.scalars(statement).all())

    def _event_to_payload(self, event: InteractionEvent) -> dict[str, Any]:
        return {
            "stage": event.stage,
            "source": event.source,
            "payload": dict(event.payload or {}),
            "created_at": event.created_at,
        }

    def _extract_audio_input(
        self,
        metadata: dict[str, object],
    ) -> dict[str, object] | None:
        audio_input = metadata.get("audio_input")
        if isinstance(audio_input, dict):
            return audio_input
        return None

    def _sanitize_metadata(self, metadata: dict[str, object]) -> dict[str, object]:
        sanitized = dict(metadata)
        sanitized.pop("audio_input", None)
        return sanitized

    def _safe_string(self, value: object | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
