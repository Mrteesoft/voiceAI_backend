from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse, SessionResponse
from app.services.chat_service import ChatService

router = APIRouter(tags=["chat"])
chat_service = ChatService()
settings = get_settings()


@router.post("/chat", response_model=ChatResponse)
def create_chat_completion(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    return chat_service.handle_message(
        db=db,
        user_id=request.user_id,
        message=request.message,
        session_id=request.session_id,
        channel=request.channel,
        platform=request.platform,
        audio_reference=request.audio_reference,
        audio_input=request.audio_input.model_dump() if request.audio_input else None,
        metadata=request.metadata,
    )


@router.get("/chat/{session_id}", response_model=SessionResponse)
def get_chat_session(
    session_id: str,
    limit: int = Query(default=settings.default_history_limit, ge=1, le=200),
    db: Session = Depends(get_db),
) -> SessionResponse:
    session = chat_service.get_session(db=db, session_id=session_id, limit=limit)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return session
