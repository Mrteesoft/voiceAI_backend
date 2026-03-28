from __future__ import annotations


class BusinessLogicService:
    def evaluate(
        self,
        *,
        message: str,
        channel: str,
        platform: str,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, list[str]]:
        lowered_message = message.lower()
        normalized_metadata = metadata or {}

        actions = ["track_conversation_session"]
        integration_targets = ["analytics"]

        if channel == "voice":
            actions.append("prefer_concise_spoken_reply")

        if platform in {"whatsapp", "slack"}:
            actions.append("route_channel_connector")
            integration_targets.append(platform)

        if platform == "ivr":
            actions.append("prepare_telephony_response")
            integration_targets.append("telephony")

        if any(keyword in lowered_message for keyword in ("order", "payment", "invoice", "refund")):
            actions.append("invoke_order_workflow")
            integration_targets.append("billing")

        if any(keyword in lowered_message for keyword in ("book", "appointment", "schedule")):
            actions.append("invoke_scheduling_workflow")
            integration_targets.append("calendar")

        locale = normalized_metadata.get("locale")
        if locale:
            actions.append(f"honor_locale_{locale}")

        return {
            "actions": actions,
            "integration_targets": sorted(set(integration_targets)),
        }
