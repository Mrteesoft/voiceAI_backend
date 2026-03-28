from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Assistant Backend MVP"
    app_version: str = "0.3.0"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/assistant_db"
    model_backend: str = "mock"
    model_name: str = "demo-assistant"
    system_prompt: str = (
        "You are a helpful backend AI assistant that explains system design clearly."
    )
    log_level: str = "INFO"
    log_file_path: str | None = "./logs/app.log"
    ecs_logging_enabled: bool = True
    slow_request_threshold_ms: int = 300
    model_history_window_size: int = 12
    default_history_limit: int = 50
    default_document_limit: int = 50
    default_search_limit: int = 5
    rag_enabled: bool = True
    rag_query_history_window: int = 3
    rag_retrieval_limit: int = 4
    rag_context_char_limit: int = 1600
    embedding_backend: str = "hash"
    embedding_dimensions: int = 384
    observability_service_name: str = "ai-assistant-backend"
    prometheus_enabled: bool = True
    prometheus_metrics_path: str = "/metrics"
    otel_enabled: bool = True
    otel_exporter_otlp_endpoint: str | None = "http://localhost:4318"
    otel_exporter_otlp_headers: str | None = None
    sentry_enabled: bool = False
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1
    sentry_profiles_sample_rate: float = 0.0
    datadog_enabled: bool = False
    datadog_service: str = "ai-assistant-backend"
    datadog_env: str = "development"
    datadog_version: str = "0.3.0"
    new_relic_enabled: bool = False
    new_relic_config_file: str | None = "./observability/newrelic/newrelic.ini"
    new_relic_environment: str | None = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
