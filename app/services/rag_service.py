from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.retrieval import RetrievalService


@dataclass(slots=True)
class RAGContextItem:
    chunk_id: str | None
    content: str
    document_title: str | None
    score: float
    retrieval_strategy: str
    citation: str


@dataclass(slots=True)
class RAGResult:
    retrieval_query: str
    context_items: list[RAGContextItem]
    context_texts: list[str]
    citations: list[str]
    grounded_prompt: str


class RAGService:
    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = settings.rag_enabled
        self.query_history_window = settings.rag_query_history_window
        self.retrieval_limit = settings.rag_retrieval_limit
        self.context_char_limit = settings.rag_context_char_limit
        self.retrieval_service = RetrievalService()

    def prepare_generation_context(
        self,
        *,
        db: Session,
        user_message: str,
        history: list[dict[str, str]],
    ) -> RAGResult:
        retrieval_query = self._build_retrieval_query(
            user_message=user_message,
            history=history,
        )
        raw_results = self.retrieval_service.search(
            db=db,
            query=retrieval_query,
            limit=self.retrieval_limit,
        )
        context_items = self._normalize_results(raw_results)
        context_texts = [item.content for item in context_items]
        citations = list(dict.fromkeys(item.citation for item in context_items))
        grounded_prompt = self._build_grounded_prompt(
            user_message=user_message,
            context_items=context_items,
        )
        return RAGResult(
            retrieval_query=retrieval_query,
            context_items=context_items,
            context_texts=context_texts,
            citations=citations,
            grounded_prompt=grounded_prompt,
        )

    def _build_retrieval_query(
        self,
        *,
        user_message: str,
        history: list[dict[str, str]],
    ) -> str:
        if not self.enabled:
            return user_message.strip()

        prior_user_turns = [
            item["content"].strip()
            for item in history
            if item.get("role") == "user" and item.get("content", "").strip()
        ]
        selected_turns = prior_user_turns[-self.query_history_window :]
        query_parts = list(dict.fromkeys([*selected_turns, user_message.strip()]))
        return " | ".join(part for part in query_parts if part)

    def _normalize_results(
        self,
        raw_results: list[dict[str, str | float | None]],
    ) -> list[RAGContextItem]:
        normalized: list[RAGContextItem] = []
        seen: set[tuple[str | None, str]] = set()
        remaining_chars = self.context_char_limit

        for index, item in enumerate(raw_results, start=1):
            content = str(item.get("content") or "").strip()
            if not content:
                continue

            document_title = self._safe_string(item.get("document_title")) or "knowledge-base"
            dedupe_key = (document_title, content)
            if dedupe_key in seen:
                continue

            if remaining_chars <= 0:
                break

            clipped_content = content[:remaining_chars].strip()
            if not clipped_content:
                break

            seen.add(dedupe_key)
            citation = f"{document_title}#{index}"
            normalized.append(
                RAGContextItem(
                    chunk_id=self._safe_string(item.get("chunk_id")),
                    content=clipped_content,
                    document_title=document_title,
                    score=float(item.get("score") or 0.0),
                    retrieval_strategy=self._safe_string(item.get("retrieval_strategy")) or "unknown",
                    citation=citation,
                )
            )
            remaining_chars -= len(clipped_content)

        return normalized

    def _build_grounded_prompt(
        self,
        *,
        user_message: str,
        context_items: list[RAGContextItem],
    ) -> str:
        if not context_items:
            return (
                "No retrieval context was found. Answer carefully and say when the knowledge base "
                "does not contain enough information."
            )

        source_lines = [
            (
                f"{item.citation} "
                f"(strategy={item.retrieval_strategy}, score={item.score:.2f}): {item.content}"
            )
            for item in context_items
        ]
        sources_block = "\n".join(source_lines)
        return (
            "Use the retrieved knowledge below to answer the user's request. "
            "Prefer grounded statements, mention uncertainty when context is incomplete, "
            "and cite sources by their citation label when summarizing retrieved facts.\n"
            f"User request: {user_message}\n"
            f"Retrieved sources:\n{sources_block}"
        )

    def _safe_string(self, value: object | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
