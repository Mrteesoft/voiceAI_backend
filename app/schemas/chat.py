from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PlatformType = Literal["web", "mobile", "whatsapp", "slack", "ivr", "api"]


class AudioInputPayload(BaseModel):
    audio_base64: str = Field(..., min_length=1)
    audio_format: str = Field(default="wav", min_length=1, max_length=20)
    sample_rate_hz: int | None = Field(default=None, ge=8000, le=192000)
    transcript_hint: str | None = Field(default=None, max_length=4000)


class VoiceResponsePayload(BaseModel):
    transport: str
    audio_format: str
    sample_rate_hz: int | None = None
    voice_prompt: str
    audio_base64: str | None = None


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    message: str = Field(default="", max_length=4000)
    session_id: str | None = Field(default=None)
    channel: Literal["text", "voice"] = "text"
    platform: PlatformType = "web"
    audio_reference: str | None = Field(default=None, max_length=2000)
    audio_input: AudioInputPayload | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_content(self) -> "ChatRequest":
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


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str
    created_at: datetime


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    history: list[MessageResponse]


class ChatResponse(SessionResponse):
    reply: str
    context_used: list[str]
    retrieval_query: str
    citations: list[str] = Field(default_factory=list)
    platform: PlatformType
    pipeline_run_id: str
    business_actions: list[str] = Field(default_factory=list)
    voice_response: VoiceResponsePayload | None = None
    has_audio_input: bool = False
