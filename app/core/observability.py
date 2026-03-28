from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.metrics import metrics_asgi_app

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.engine import Engine

logger = logging.getLogger("app.observability")
_vendor_agents_bootstrapped = False
_metrics_mounted = False
_otel_configured = False
_sentry_configured = False


def bootstrap_vendor_agents() -> None:
    global _vendor_agents_bootstrapped
    if _vendor_agents_bootstrapped:
        return

    settings = get_settings()

    if settings.datadog_enabled:
        os.environ.setdefault("DD_SERVICE", settings.datadog_service)
        os.environ.setdefault("DD_ENV", settings.datadog_env)
        os.environ.setdefault("DD_VERSION", settings.datadog_version or settings.app_version)
        import ddtrace.auto  # noqa: F401

        logger.info("datadog_auto_instrumentation_enabled")

    if settings.new_relic_enabled:
        import newrelic.agent

        newrelic.agent.initialize(
            settings.new_relic_config_file or None,
            settings.new_relic_environment or None,
        )
        logger.info(
            "new_relic_initialized config_file=%s environment=%s",
            settings.new_relic_config_file or "env",
            settings.new_relic_environment or "default",
        )

    _vendor_agents_bootstrapped = True


def setup_observability(app: "FastAPI", engine: "Engine") -> None:
    global _metrics_mounted, _otel_configured, _sentry_configured

    settings = get_settings()

    if settings.prometheus_enabled and not _metrics_mounted:
        app.mount(settings.prometheus_metrics_path, metrics_asgi_app())
        _metrics_mounted = True
        logger.info("prometheus_metrics_enabled path=%s", settings.prometheus_metrics_path)

    if settings.otel_enabled and not _otel_configured:
        _configure_open_telemetry(app=app, engine=engine)
        _otel_configured = True

    if settings.sentry_enabled and settings.sentry_dsn and not _sentry_configured:
        _configure_sentry()
        _sentry_configured = True


def _configure_open_telemetry(app: "FastAPI", engine: "Engine") -> None:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    settings = get_settings()
    resource = Resource.create(
        {
            "service.name": settings.observability_service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.app_env,
        }
    )
    tracer_provider = TracerProvider(resource=resource)

    if settings.otel_exporter_otlp_endpoint:
        headers = _parse_headers(settings.otel_exporter_otlp_headers)
        span_exporter = OTLPSpanExporter(
            endpoint=_normalize_otlp_trace_endpoint(settings.otel_exporter_otlp_endpoint),
            headers=headers,
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))

    trace.set_tracer_provider(tracer_provider)
    LoggingInstrumentor().instrument(set_logging_format=False)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
    logger.info("opentelemetry_enabled endpoint=%s", settings.otel_exporter_otlp_endpoint)


def _configure_sentry() -> None:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    settings = get_settings()
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.app_version,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
    )
    logger.info("sentry_enabled")


def _normalize_otlp_trace_endpoint(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    if normalized.endswith("/v1/traces"):
        return normalized
    return f"{normalized}/v1/traces"


def _parse_headers(raw_headers: str | None) -> dict[str, str] | None:
    if not raw_headers:
        return None

    headers: dict[str, str] = {}
    for item in raw_headers.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        headers[key.strip()] = value.strip()

    return headers or None
