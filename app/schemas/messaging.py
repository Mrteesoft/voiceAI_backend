from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.chat import AudioInputPayload, PlatformType


class QueueMessageRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    message: str = Field(default="", max_length=4000)
    session_id: str | None = Field(default=None)
    channel: Literal["text", "voice"] = "text"
    platform: PlatformType = "web"
    audio_reference: str | None = Field(default=None, max_length=2000)
    audio_input: AudioInputPayload | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_content(self) -> "QueueMessageRequest":
        if self.channel == "text" and not self.message.strip():
            raise ValueError("Text requests require a non-empty message.")

        if self.channel == "voice":
            has_transcript_text = bool(self.message.strip())
            has_audio = self.audio_input is not None or self.audio_reference is not None
            has_transcript_hint = bool(str(self.metadata.get("transcript", "")).strip())
            if not (has_transcript_text or has_audio or has_transcript_hint):
                raise ValueError(
                    "Voice requests require message text, audio_input, audio_reference, or metadata.transcript."
                )

        return self


class MessageJobResponse(BaseModel):
    job_id: str
    status: str
    user_id: str
    session_id: str | None
    channel: str
    platform: str
    input_text: str
    audio_reference: str | None
    has_audio_input: bool
    audio_input_format: str | None
    metadata: dict[str, object]
    transcript: str | None
    reply: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
