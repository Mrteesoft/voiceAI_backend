from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.metrics import record_websocket_event
from app.db.session import SessionLocal
from app.services.chat_service import ChatService

router = APIRouter(tags=["realtime"])
chat_service = ChatService()


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        while True:
            payload = await websocket.receive_json()
            channel = payload.get("channel", "text")
            record_websocket_event(channel=channel, event="received")
            db = SessionLocal()
            try:
                async for event in chat_service.stream_message(
                    db=db,
                    user_id=payload["user_id"],
                    message=payload.get("message", ""),
                    session_id=payload.get("session_id"),
                    channel=channel,
                    platform=payload.get("platform", "web"),
                    audio_reference=payload.get("audio_reference"),
                    audio_input=payload.get("audio_input"),
                    metadata=payload.get("metadata") or {},
                ):
                    record_websocket_event(channel=channel, event=str(event.get("event", "unknown")))
                    await websocket.send_json(event)
            except KeyError as exc:
                record_websocket_event(channel=channel, event="error")
                await websocket.send_json(
                    {
                        "event": "error",
                        "detail": f"Missing field: {exc.args[0]}",
                    }
                )
            except Exception as exc:
                record_websocket_event(channel=channel, event="error")
                await websocket.send_json(
                    {
                        "event": "error",
                        "detail": str(exc),
                    }
                )
            finally:
                db.close()
    except WebSocketDisconnect:
        return
