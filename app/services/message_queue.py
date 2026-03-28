from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from app.core.metrics import record_async_job, set_message_queue_depth
from app.db.models import AsyncMessageJob
from app.db.session import SessionLocal
from app.services.chat_service import ChatService


class MessageQueueService:
    def __init__(self) -> None:
        self.chat_service = ChatService()
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())
        set_message_queue_depth(self.queue_size())

    async def stop(self) -> None:
        if self._worker_task is None:
            return

        await self._queue.put(None)
        set_message_queue_depth(self.queue_size())
        await self._worker_task
        self._worker_task = None

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(job_id)
        set_message_queue_depth(self.queue_size())

    def queue_size(self) -> int:
        return self._queue.qsize()

    def create_job(
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
    ) -> AsyncMessageJob:
        request_metadata = dict(metadata or {})
        if audio_input is not None:
            request_metadata["audio_input"] = audio_input
        transcript_hint = None
        if isinstance(request_metadata.get("transcript"), str):
            transcript_hint = str(request_metadata["transcript"]).strip() or None

        job = AsyncMessageJob(
            user_id=user_id,
            session_id=session_id,
            channel=channel,
            platform=platform,
            input_text=message,
            audio_reference=audio_reference,
            request_metadata=request_metadata,
            transcript=(transcript_hint or message.strip() or None) if channel == "voice" else None,
            status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        record_async_job(channel=channel, status="queued")
        return job

    def get_job(self, db: Session, job_id: str) -> AsyncMessageJob | None:
        return db.get(AsyncMessageJob, job_id)

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self._queue.get()
            set_message_queue_depth(self.queue_size())
            if job_id is None:
                self._queue.task_done()
                set_message_queue_depth(self.queue_size())
                break

            try:
                await self._process_job(job_id)
            finally:
                self._queue.task_done()
                set_message_queue_depth(self.queue_size())

    async def _process_job(self, job_id: str) -> None:
        db = SessionLocal()
        try:
            job = db.get(AsyncMessageJob, job_id)
            if job is None:
                return

            job.status = "processing"
            db.commit()
            record_async_job(channel=job.channel, status="processing")

            response = self.chat_service.handle_message(
                db=db,
                user_id=job.user_id,
                message=job.transcript or job.input_text,
                session_id=job.session_id,
                channel=job.channel,
                platform=job.platform,
                audio_reference=job.audio_reference,
                audio_input=self._extract_audio_input(job.request_metadata),
                metadata=job.request_metadata,
            )

            job.status = "completed"
            job.session_id = response.session_id
            job.reply = response.reply
            db.commit()
            record_async_job(channel=job.channel, status="completed")
        except Exception as exc:
            db.rollback()
            failed_job = db.get(AsyncMessageJob, job_id)
            if failed_job is not None:
                failed_job.status = "failed"
                failed_job.error_message = str(exc)
                db.commit()
                record_async_job(channel=failed_job.channel, status="failed")
        finally:
            db.close()

    def _extract_audio_input(self, metadata: dict[str, object]) -> dict[str, object] | None:
        audio_input = metadata.get("audio_input")
        if isinstance(audio_input, dict):
            return audio_input
        return None


message_queue_service = MessageQueueService()
