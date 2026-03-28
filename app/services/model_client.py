from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Protocol

from app.core.config import get_settings


class ModelClient(Protocol):
    def generate_reply(
        self,
        user_message: str,
        history: list[dict[str, str]],
        context: list[str],
        channel: str = "text",
        platform: str = "web",
        business_actions: list[str] | None = None,
        retrieval_query: str | None = None,
        citations: list[str] | None = None,
        rag_prompt: str | None = None,
    ) -> str:
        ...

    async def stream_reply(
        self,
        user_message: str,
        history: list[dict[str, str]],
        context: list[str],
        channel: str = "text",
        platform: str = "web",
        business_actions: list[str] | None = None,
        retrieval_query: str | None = None,
        citations: list[str] | None = None,
        rag_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        ...


class MockModelClient:
    def __init__(self, model_name: str, system_prompt: str) -> None:
        self.model_name = model_name
        self.system_prompt = system_prompt

    def generate_reply(
        self,
        user_message: str,
        history: list[dict[str, str]],
        context: list[str],
        channel: str = "text",
        platform: str = "web",
        business_actions: list[str] | None = None,
        retrieval_query: str | None = None,
        citations: list[str] | None = None,
        rag_prompt: str | None = None,
    ) -> str:
        return self._compose_reply(
            user_message=user_message,
            history=history,
            context=context,
            channel=channel,
            platform=platform,
            business_actions=business_actions,
            retrieval_query=retrieval_query,
            citations=citations,
            rag_prompt=rag_prompt,
        )

    async def stream_reply(
        self,
        user_message: str,
        history: list[dict[str, str]],
        context: list[str],
        channel: str = "text",
        platform: str = "web",
        business_actions: list[str] | None = None,
        retrieval_query: str | None = None,
        citations: list[str] | None = None,
        rag_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        reply = self._compose_reply(
            user_message=user_message,
            history=history,
            context=context,
            channel=channel,
            platform=platform,
            business_actions=business_actions,
            retrieval_query=retrieval_query,
            citations=citations,
            rag_prompt=rag_prompt,
        )
        for token in reply.split():
            yield f"{token} "
            await asyncio.sleep(0.03)

    def _compose_reply(
        self,
        user_message: str,
        history: list[dict[str, str]],
        context: list[str],
        channel: str = "text",
        platform: str = "web",
        business_actions: list[str] | None = None,
        retrieval_query: str | None = None,
        citations: list[str] | None = None,
        rag_prompt: str | None = None,
    ) -> str:
        context_block = " | ".join(context) if context else "No extra context found."
        turn_count = len(history)
        action_block = ", ".join(business_actions or ["track_conversation_session"])
        citation_block = ", ".join(citations or ["no-citations"])
        rag_block = rag_prompt or "No RAG prompt supplied."
        transport = (
            "a voice pipeline that receives transcripts and emits audio-ready responses"
            if channel == "voice"
            else "a text pipeline that can stream partial tokens over WebSockets"
        )
        return (
            f"[{self.model_name}] Based on your message, the backend should route the request "
            f"through an orchestrator, attach retrieved context, and store the conversation. "
            f"This request is using {transport} on the {platform} platform. "
            f"Business actions in scope: {action_block}. "
            f"Retrieval query: {retrieval_query or user_message}. "
            f"Sources: {citation_block}. "
            f"Relevant context: {context_block}. "
            f"Grounding instructions: {rag_block}. "
            f"Conversation turns stored so far: {turn_count}. "
            f"Latest user intent: {user_message}"
        )


def get_model_client() -> ModelClient:
    settings = get_settings()

    if settings.model_backend == "mock":
        return MockModelClient(
            model_name=settings.model_name,
            system_prompt=settings.system_prompt,
        )

    raise ValueError(
        f"Unsupported MODEL_BACKEND '{settings.model_backend}'. "
        "Add a real provider adapter in app/services/model_client.py."
    )
