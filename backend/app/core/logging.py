import logging
import sys
from typing import cast

import structlog

from app.core.config import settings


def setup_logging() -> None:
    """
    Configures structlog for the application.

    - Development: human-friendly coloured console output
    - Production: JSON output for log aggregators (Railway, Datadog, etc.)
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    renderer: structlog.processors.JSONRenderer | structlog.dev.ConsoleRenderer

    if settings.is_production:
        # JSON output — structured and machine-readable for log aggregators
        renderer = structlog.processors.JSONRenderer()
    else:
        # Pretty coloured output for local development
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(
        logging.INFO if settings.is_production else logging.DEBUG)

    # Quieten noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Returns a structlog logger bound to the given name.
    Usage: logger = get_logger(__name__)
    """
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
