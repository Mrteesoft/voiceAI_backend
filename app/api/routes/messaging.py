from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.messaging import MessageJobResponse, QueueMessageRequest
from app.services.message_queue import message_queue_service

router = APIRouter(tags=["messaging"])


def _to_job_response(job) -> MessageJobResponse:
    audio_input = job.request_metadata.get("audio_input") if isinstance(job.request_metadata, dict) else None
    audio_input_format = None
    if isinstance(audio_input, dict):
        audio_input_format = str(audio_input.get("audio_format")) if audio_input.get("audio_format") else None

    metadata = dict(job.request_metadata or {})
    metadata.pop("audio_input", None)
    return MessageJobResponse(
        job_id=job.id,
        status=job.status,
        user_id=job.user_id,
        session_id=job.session_id,
        channel=job.channel,
        platform=job.platform,
        input_text=job.input_text,
        audio_reference=job.audio_reference,
        has_audio_input=isinstance(audio_input, dict),
        audio_input_format=audio_input_format,
        metadata=metadata,
        transcript=job.transcript,
        reply=job.reply,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post("/messages/jobs", response_model=MessageJobResponse, status_code=202)
async def queue_message(
    request: QueueMessageRequest,
    db: Session = Depends(get_db),
) -> MessageJobResponse:
    job = message_queue_service.create_job(
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
    await message_queue_service.enqueue(job.id)
    return _to_job_response(job)


@router.get("/messages/jobs/{job_id}", response_model=MessageJobResponse)
def get_message_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> MessageJobResponse:
    job = message_queue_service.get_job(db=db, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return _to_job_response(job)
