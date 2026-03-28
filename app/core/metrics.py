from __future__ import annotations

from contextlib import contextmanager

from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

HTTP_REQUESTS_TOTAL = Counter(
    "app_http_requests_total",
    "Total HTTP requests processed by the application.",
    ("method", "route", "status_code"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "app_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "route"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "app_http_requests_in_progress",
    "HTTP requests currently being processed.",
)
ASYNC_MESSAGE_JOBS_TOTAL = Counter(
    "app_async_message_jobs_total",
    "Async message jobs by channel and status.",
    ("channel", "status"),
)
MESSAGE_QUEUE_DEPTH = Gauge(
    "app_message_queue_depth",
    "Current in-memory async message queue depth.",
)
WEBSOCKET_EVENTS_TOTAL = Counter(
    "app_websocket_events_total",
    "WebSocket events emitted by channel and event type.",
    ("channel", "event"),
)


def metrics_asgi_app():
    return make_asgi_app()


@contextmanager
def track_in_progress_requests():
    HTTP_REQUESTS_IN_PROGRESS.inc()
    try:
        yield
    finally:
        HTTP_REQUESTS_IN_PROGRESS.dec()


def observe_http_request(method: str, route: str, status_code: int, duration_seconds: float) -> None:
    normalized_route = route or "unknown"
    HTTP_REQUESTS_TOTAL.labels(
        method=method,
        route=normalized_route,
        status_code=str(status_code),
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        method=method,
        route=normalized_route,
    ).observe(duration_seconds)


def record_async_job(channel: str, status: str) -> None:
    ASYNC_MESSAGE_JOBS_TOTAL.labels(channel=channel, status=status).inc()


def set_message_queue_depth(depth: int) -> None:
    MESSAGE_QUEUE_DEPTH.set(depth)


def record_websocket_event(channel: str, event: str) -> None:
    WEBSOCKET_EVENTS_TOTAL.labels(channel=channel, event=event).inc()
