from __future__ import annotations

from app.services.interaction_pipeline import InteractionPipelineService
from app.services.knowledge_service import KnowledgeService


def test_process_interaction_records_pipeline_events_and_voice_output(db_session) -> None:
    KnowledgeService().seed_defaults(db_session)
    service = InteractionPipelineService()

    result = service.process_interaction(
        db=db_session,
        user_id="tester",
        message="Schedule a payment reminder for tomorrow morning.",
        channel="voice",
        platform="ivr",
        metadata={"locale": "en-NG"},
    )

    assert result["run_id"]
    assert result["session_id"]
    assert result["reply"]
    assert result["voice_response"] is not None
    assert result["voice_response"]["transport"] == "sip-bridge"
    assert "prefer_concise_spoken_reply" in result["business_actions"]
    assert "invoke_order_workflow" in result["business_actions"]
    assert "invoke_scheduling_workflow" in result["business_actions"]

    persisted = service.get_run_response(db=db_session, run_id=result["run_id"])
    assert persisted is not None
    assert persisted["metadata"]["locale"] == "en-NG"
    assert persisted["transcript"] == "Schedule a payment reminder for tomorrow morning."
    assert [event["stage"] for event in persisted["events"]] == [
        "input_received",
        "input_normalized",
        "context_loaded",
        "business_logic_applied",
        "model_completed",
        "voice_response_ready",
        "response_ready",
    ]
