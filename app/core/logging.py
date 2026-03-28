from __future__ import annotations

import logging
from pathlib import Path

import ecs_logging
from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    formatter: logging.Formatter
    if settings.ecs_logging_enabled:
        formatter = ecs_logging.StdlibFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if settings.log_file_path:
        log_path = Path(settings.log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    for handler in handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)

    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,
    )
