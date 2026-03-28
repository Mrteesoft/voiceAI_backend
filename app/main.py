from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from sqlalchemy import text

from app.core.logging import configure_logging

configure_logging()

from app.core.config import get_settings
from app.core.metrics import observe_http_request, track_in_progress_requests
from app.core.observability import bootstrap_vendor_agents, setup_observability

bootstrap_vendor_agents()

from fastapi import FastAPI, Request

from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.interactions import router as interactions_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.messaging import router as messaging_router
from app.api.routes.realtime import router as realtime_router
from app.db import models  # noqa: F401
from app.db.session import Base, SessionLocal, engine
from app.services.knowledge_service import KnowledgeService
from app.services.message_queue import message_queue_service

settings = get_settings()
knowledge_service = KnowledgeService()
logger = logging.getLogger("app.http")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        knowledge_service.seed_defaults(db)
        knowledge_service.backfill_missing_embeddings(db)
    await message_queue_service.start()
    yield
    await message_queue_service.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)
setup_observability(app=app, engine=engine)

app.include_router(health_router)
app.include_router(chat_router, prefix=settings.api_prefix)
app.include_router(interactions_router, prefix=settings.api_prefix)
app.include_router(knowledge_router, prefix=settings.api_prefix)
app.include_router(messaging_router, prefix=settings.api_prefix)
app.include_router(realtime_router, prefix=settings.api_prefix)


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    request_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    with track_in_progress_requests():
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            observe_http_request(
                method=request.method,
                route=request.url.path,
                status_code=500,
                duration_seconds=duration_ms / 1000,
            )
            logger.exception(
                "request_failed method=%s path=%s duration_ms=%.2f request_id=%s",
                request.method,
                request.url.path,
                duration_ms,
                request_id,
            )
            raise

    duration_ms = (time.perf_counter() - started) * 1000
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    observe_http_request(
        method=request.method,
        route=route_path,
        status_code=response.status_code,
        duration_seconds=duration_ms / 1000,
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
    log_level = (
        logging.WARNING
        if duration_ms >= settings.slow_request_threshold_ms
        else logging.INFO
    )
    logger.log(
        log_level,
        "request_completed method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
        request.method,
        route_path,
        response.status_code,
        duration_ms,
        request_id,
    )
    return response


@app.get("/", tags=["root"])
def read_root() -> dict[str, str]:
    return {
        "message": "AI assistant backend MVP is running.",
        "docs": "/docs",
    }
