"""
Structured JSON logging. The event schema matches the frontend logger
(frontend/src/services/logger.js) so one CloudWatch Logs Insights query
covers both services.
"""

import atexit
import json
import logging
import os
import sys
from datetime import datetime, timezone

from backend.observability.context import get_trace_id

DEFAULT_SERVICE_NAME = "geoyield-api"

# Logger name for browser events re-emitted from POST /api/logs.
FRONTEND_LOGGER_NAME = "geoyield.frontend"

# "direccion" is here for GDPR: the address typed into the geocoder is
# personal data.
REDACT_KEYS = frozenset(
    {
        "direccion", "address", "email", "password", "passwd", "secret",
        "token", "authorization", "api_key", "apikey", "access_key",
        "secret_key", "database_url", "gemini_api_key", "anthropic_api_key",
    }
)

REDACTED = "[REDACTED]"

# Libraries that emit a line per HTTP request or per signed AWS call.
NOISY_LOGGERS = (
    "httpx", "httpx2", "httpcore", "urllib3", "asyncio", "botocore", "boto3",
    "s3transfer", "watchtower", "sentence_transformers", "sqlalchemy.engine",
)

# CloudWatch allows 256 KB per event; stay well below it.
MAX_MESSAGE_CHARS = 16_000

_STANDARD_RECORD_ATTRS = frozenset(
    {
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "module", "msecs",
        "message", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "taskName", "thread", "threadName",
    }
)

# Top-level schema keys. Keeping this closed is what makes Logs Insights
# queries stable; anything else is nested under "context".
RESERVED_KEYS = frozenset(
    {
        "timestamp", "level", "service", "env", "version", "logger", "message",
        "trace_id", "session_id", "event", "duration_ms", "error", "context",
    }
)

_configured = False
_cloudwatch_handler: logging.Handler | None = None

_LEVEL_COLOURS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[35m",
}
_RESET = "\033[0m"


def is_production(env: str | None = None) -> bool:
    value = (env if env is not None else os.getenv("ENV", "development")).strip().lower()
    return value in ("production", "prod")


def _use_colour() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def _parse_level(raw: str | None) -> int:
    """Accepts a number ("20") or a name ("INFO"). Invalid values give INFO."""
    if raw is None or not str(raw).strip():
        return logging.INFO

    value = str(raw).strip()
    if value.isdigit():
        return int(value)

    level = logging.getLevelName(value.upper())
    return level if isinstance(level, int) else logging.INFO


def redact(value, _depth: int = 0):
    """Copy of `value` with sensitive keys replaced. Depth-capped against cycles."""
    if _depth > 6:
        return "[...]"

    if isinstance(value, dict):
        return {
            key: (
                REDACTED
                if isinstance(key, str) and key.lower() in REDACT_KEYS
                else redact(subvalue, _depth + 1)
            )
            for key, subvalue in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [redact(item, _depth + 1) for item in value]

    return value


def _truncate(text: str, limit: int = MAX_MESSAGE_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"... [truncated, {len(text)} chars]"


class ContextFilter(logging.Filter):
    """Injects the current request's trace id into every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "trace_id", None):
            trace_id = get_trace_id()
            if trace_id:
                record.trace_id = trace_id
        return True


class JsonFormatter(logging.Formatter):
    """One JSON line per event. CloudWatch splits on newlines."""

    def __init__(self, service: str, env: str, version: str):
        super().__init__()
        self.service = service
        self.env = env
        self.version = version

    def format(self, record: logging.LogRecord) -> str:
        # Browser events keep the client's timestamp, not the receive time.
        timestamp = getattr(record, "timestamp", None) or datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat(timespec="milliseconds").replace("+00:00", "Z")

        payload = {
            "timestamp": timestamp,
            "level": record.levelname,
            "service": getattr(record, "service", None) or self.service,
            "env": self.env,
            "version": self.version,
            # `logger_name` carries the client's logger name as a field. It is
            # never passed to getLogger(), which a browser could use to grow
            # the logging registry without bound.
            "logger": getattr(record, "logger_name", None) or record.name,
            "message": _truncate(record.getMessage()),
        }

        for key in ("trace_id", "session_id", "event", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        error = getattr(record, "error", None)
        if error is None and record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            error = {
                "type": exc_type.__name__ if exc_type else None,
                "message": str(exc_value) if exc_value else None,
                "stack": _truncate(self.formatException(record.exc_info)),
            }
        if error:
            payload["error"] = redact(error)

        context = dict(getattr(record, "context", None) or {})
        for key, value in record.__dict__.items():
            if (
                key not in _STANDARD_RECORD_ATTRS
                and key not in RESERVED_KEYS
                and key != "logger_name"
                and not key.startswith("_")
            ):
                context.setdefault(key, value)

        if context:
            payload["context"] = redact(context)

        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Readable format for local development."""

    def __init__(self, colour: bool = False):
        super().__init__(
            fmt="%(asctime)s %(levelname)-8s %(name)s%(trace_suffix)s - %(message)s",
            datefmt="%H:%M:%S",
        )
        self.colour = colour

    def format(self, record: logging.LogRecord) -> str:
        trace_id = getattr(record, "trace_id", None)
        record.trace_suffix = f" [{trace_id}]" if trace_id else ""

        context = getattr(record, "context", None)
        error = getattr(record, "error", None)

        line = super().format(record)
        if context:
            line += f" | {json.dumps(redact(context), ensure_ascii=False, default=str)}"
        # Browser events carry a pre-built error object rather than exc_info.
        if error and not record.exc_info:
            line += f"\n    {error.get('type')}: {error.get('message')}"

        if self.colour:
            prefix = _LEVEL_COLOURS.get(record.levelname, "")
            if prefix:
                line = f"{prefix}{line}{_RESET}"
        return line


def tame_third_party_loggers() -> None:
    """
    Routes uvicorn through the root logger and floors noisy libraries.

    Idempotent, and must stay callable after uvicorn installs its own config:
    a CLI start configures logging after this module is imported, so the
    lifespan calls it again.
    """
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    # Duplicates the request middleware, which also carries trace_id.
    logging.getLogger("uvicorn.access").disabled = True

    # Applied at any root level: DEBUG is the local default, and this chatter
    # would bury our own lines.
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def configure_logging(force: bool = False) -> None:
    """Configures the root logger. Idempotent, so it cannot duplicate handlers."""
    global _configured, _cloudwatch_handler

    if _configured and not force:
        return

    service = os.getenv("SERVICE_NAME", DEFAULT_SERVICE_NAME)
    env = os.getenv("ENV", "development")
    version = os.getenv("SERVICE_VERSION", "0.0.0")
    production = is_production(env)

    # JSON at INFO in production, readable text at DEBUG anywhere else.
    log_format = (os.getenv("LOG_FORMAT") or ("json" if production else "text")).strip().lower()
    level = _parse_level(os.getenv("LOG_LEVEL") or ("INFO" if production else "DEBUG"))

    formatter: logging.Formatter
    if log_format == "text":
        formatter = TextFormatter(colour=_use_colour())
    else:
        formatter = JsonFormatter(service=service, env=env, version=version)

    root = logging.getLogger()

    _close_cloudwatch_handler()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    root.setLevel(level)
    context_filter = ContextFilter()

    # stdout is what the awslogs/FireLens drivers collect.
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)
    root.addHandler(stream_handler)

    log_file = os.getenv("LOG_FILE", "").strip()
    if log_file:
        from pathlib import Path

        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        root.addHandler(file_handler)

    # Before building the handler: botocore logs during credential negotiation.
    tame_third_party_loggers()

    from backend.observability.cloudwatch import build_cloudwatch_handler

    _cloudwatch_handler = build_cloudwatch_handler()
    if _cloudwatch_handler is not None:
        _cloudwatch_handler.setFormatter(formatter)
        _cloudwatch_handler.addFilter(context_filter)
        root.addHandler(_cloudwatch_handler)
        atexit.register(_close_cloudwatch_handler)

    tame_third_party_loggers()
    _configured = True


def _close_cloudwatch_handler() -> None:
    """close() flushes the queue, so skipping it loses the last seconds of logs."""
    global _cloudwatch_handler
    if _cloudwatch_handler is not None:
        try:
            _cloudwatch_handler.flush()
            _cloudwatch_handler.close()
        except Exception:  # pragma: no cover
            pass
        logging.getLogger().removeHandler(_cloudwatch_handler)
        _cloudwatch_handler = None


def shutdown_logging() -> None:
    _close_cloudwatch_handler()
    logging.shutdown()


def get_logger(name: str) -> logging.Logger:
    if not name.startswith("geoyield"):
        name = f"geoyield.{name}"
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int | str,
    message: str,
    *,
    event: str | None = None,
    duration_ms: float | None = None,
    error: dict | None = None,
    **context,
) -> None:
    """Emits an event with structured context; kwargs land under "context"."""
    resolved_level = _parse_level(level) if isinstance(level, str) else level

    extra: dict = {}
    if event is not None:
        extra["event"] = event
    if duration_ms is not None:
        extra["duration_ms"] = round(duration_ms, 2)
    if error is not None:
        extra["error"] = error
    if context:
        extra["context"] = context

    logger.log(resolved_level, message, extra=extra)
