"""Logging configuration using structlog."""

import logging
import sys
from typing import Any, cast

import hashlib
import structlog
from structlog.types import EventDict, Processor

from src.config.settings import settings


def _looks_like_vector(value: object) -> bool:
    if not isinstance(value, (list, tuple)):
        return False
    if len(value) < 50:
        return False
    return all(isinstance(x, (int, float)) for x in value)


def _summarize_vector(value: list[object] | tuple[object, ...]) -> dict[str, object]:
    sample = list(value[:3])
    raw = ",".join(str(x) for x in sample)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return {"_type": "vector", "len": len(value), "sample": sample, "sha": digest}


def _sanitize_value(value: object) -> object:
    if _looks_like_vector(value):
        return _summarize_vector(value)  # type: ignore[arg-type]

    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_sanitize_value(v) for v in value]

    if isinstance(value, str) and len(value) > 2000:
        return value[:1999] + "…"

    return value


def sanitize_log_event(_: object, __: str, event_dict: EventDict) -> EventDict:
    """Sanitize log events to avoid giant/sensitive payloads.

    - Replaces large numeric vectors with a short summary
    - Truncates very long strings
    """

    return cast(EventDict, {k: _sanitize_value(v) for k, v in event_dict.items()})


def setup_logging() -> None:
    """Configure structured logging for the application."""

    # Determine if we're in development mode
    is_development = settings.environment == "development"

    # Shared processors for all loggers
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        sanitize_log_event,
        structlog.stdlib.ExtraAdder(),
    ]

    if is_development:
        # Development: pretty console output
        processors: list[Processor] = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON output
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> Any:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
