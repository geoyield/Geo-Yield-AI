"""Structured JSON logging, sharing one event schema with the frontend."""

from backend.observability.context import (
    get_trace_id,
    new_trace_id,
    reset_trace_id,
    set_trace_id,
)
from backend.observability.logging_config import (
    FRONTEND_LOGGER_NAME,
    configure_logging,
    get_logger,
    log_event,
    shutdown_logging,
    tame_third_party_loggers,
)

__all__ = [
    "FRONTEND_LOGGER_NAME",
    "configure_logging",
    "get_logger",
    "get_trace_id",
    "log_event",
    "new_trace_id",
    "reset_trace_id",
    "set_trace_id",
    "shutdown_logging",
    "tame_third_party_loggers",
]
