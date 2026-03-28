from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.knowledge import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentResponse,
    RetrievalResultResponse,
    RetrievalSearchResponse,
)
from app.services.knowledge_service import KnowledgeService
from app.services.retrieval import RetrievalService

router = APIRouter(tags=["knowledge"])
knowledge_service = KnowledgeService()
retrieval_service = RetrievalService()
settings = get_settings()


@router.post("/knowledge/documents", response_model=KnowledgeDocumentResponse, status_code=201)
def create_knowledge_document(
    request: KnowledgeDocumentCreate,
    db: Session = Depends(get_db),
) -> KnowledgeDocumentResponse:
    document = knowledge_service.create_document(
        db=db,
        title=request.title,
        content=request.content,
        source_type=request.source_type,
    )
    return KnowledgeDocumentResponse(
        id=document.id,
        title=document.title,
        source_type=document.source_type,
        chunk_count=len(document.chunks),
        created_at=document.created_at,
    )


@router.get("/knowledge/documents", response_model=list[KnowledgeDocumentResponse])
def list_knowledge_documents(
    limit: int = Query(default=settings.default_document_limit, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[KnowledgeDocumentResponse]:
    documents = knowledge_service.list_documents_limited(db=db, limit=limit)
    return [
        KnowledgeDocumentResponse(
            id=document.id,
            title=document.title,
            source_type=document.source_type,
            chunk_count=len(document.chunks),
            created_at=document.created_at,
        )
        for document in documents
    ]


@router.get("/knowledge/search", response_model=RetrievalSearchResponse)
def search_knowledge(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=settings.default_search_limit, ge=1, le=20),
    db: Session = Depends(get_db),
) -> RetrievalSearchResponse:
    results = retrieval_service.search(db=db, query=query, limit=limit)
    return RetrievalSearchResponse(
        query=query,
        results=[
            RetrievalResultResponse(
                content=item["content"],
                score=float(item["score"]),
                document_title=item["document_title"],
            )
            for item in results
        ],
    )
