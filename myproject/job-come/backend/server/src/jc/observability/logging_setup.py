"""Enable JC's standard-library logs without enabling noisy SDK INFO logs."""
from __future__ import annotations

import logging
import sys

import structlog


def configure_application_logging(*, json_logs: bool, level: str) -> None:
    # AgentKit configures structlog's PrintLogger, not logging.getLogger('jc.*').
    # Configure only our namespace, once, so production lifecycle INFO is visible.
    logger = logging.getLogger("jc")
    handler = next((h for h in logger.handlers if getattr(h, "_jc_application", False)), None)
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
        handler._jc_application = True
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer(colors=False),
        foreign_pre_chain=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=False),
            structlog.processors.format_exc_info,
        ],
    ))
    logger.propagate = False
