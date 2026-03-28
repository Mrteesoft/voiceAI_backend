from __future__ import annotations

import base64

from app.services.interaction_pipeline import InteractionPipelineService
from app.services.knowledge_service import KnowledgeService
from app.services.voice_service import VoiceService


def test_voice_service_transcribes_text_like_audio_payload() -> None:
    service = VoiceService()
    audio_base64 = base64.b64encode(b"Schedule a payment reminder").decode("utf-8")

    result = service.transcribe_audio(
        audio_base64=audio_base64,
        audio_format="wav",
    )

    assert result["transcript"] == "Schedule a payment reminder"
    assert result["audio_size_bytes"] > 0


def test_process_interaction_accepts_audio_input_and_returns_audio_output(db_session) -> None:
    KnowledgeService().seed_defaults(db_session)
    service = InteractionPipelineService()
    audio_base64 = base64.b64encode(
        b"Schedule a payment reminder for tomorrow morning."
    ).decode("utf-8")

    result = service.process_interaction(
        db=db_session,
        user_id="tester",
        message="",
        channel="voice",
        platform="web",
        audio_input={
            "audio_base64": audio_base64,
            "audio_format": "wav",
            "sample_rate_hz": 16000,
        },
        metadata={"locale": "en-NG"},
    )

    assert result["has_audio_input"] is True
    assert result["transcript"] == "Schedule a payment reminder for tomorrow morning."
    assert result["retrieval_query"]
    assert result["citations"]
    assert result["voice_response"] is not None
    assert result["voice_response"]["audio_base64"]
    assert result["voice_response"]["audio_format"] == "wav"

    persisted = service.get_run_response(db=db_session, run_id=result["run_id"])
    assert persisted is not None
    assert persisted["has_audio_input"] is True
    assert persisted["metadata"]["locale"] == "en-NG"
    assert persisted["retrieval_query"]
    assert persisted["citations"]
    assert "audio_input" not in persisted["metadata"]
