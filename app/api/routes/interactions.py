from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.interactions import (
    InteractionRequest,
    InteractionResponse,
    InteractionRunResponse,
)
from app.services.interaction_pipeline import InteractionPipelineService

router = APIRouter(tags=["interactions"])
pipeline_service = InteractionPipelineService()


@router.post("/interactions", response_model=InteractionResponse)
def create_interaction(
    request: InteractionRequest,
    db: Session = Depends(get_db),
) -> InteractionResponse:
    result = pipeline_service.process_interaction(
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
    return InteractionResponse(**result)


@router.get("/interactions/{run_id}", response_model=InteractionRunResponse)
def get_interaction_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> InteractionRunResponse:
    run = pipeline_service.get_run_response(db=db, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Interaction run not found")

    return InteractionRunResponse(**run)
