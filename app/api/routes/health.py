from fastapi import APIRouter

from app.services.message_queue import message_queue_service

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str | int]:
    return {
        "status": "ok",
        "queue_depth": message_queue_service.queue_size(),
    }
