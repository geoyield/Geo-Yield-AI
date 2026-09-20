"""
Ingest endpoint for browser logs.

The frontend cannot reach CloudWatch without exposing AWS credentials, so it
posts batches here and the backend re-emits them through its own logger.
Public and unauthenticated, hence the caps, rate limit and sanitising below.
"""

import logging
import threading
import time

from fastapi import APIRouter, HTTPException, Request, status

from backend.api.schemas.logs import (
    MAX_CONTEXT_KEYS,
    MAX_EVENTS_PER_BATCH,
    VALID_LEVELS,
    LogEventIn,
)
from backend.observability import FRONTEND_LOGGER_NAME, get_logger

router = APIRouter(prefix="/api", tags=["logs"])

frontend_logger = get_logger(FRONTEND_LOGGER_NAME)

FRONTEND_SERVICE = "geoyield-frontend"

# Token bucket, in memory. State is per process, so with several uvicorn
# workers the effective limit scales with the worker count; move to Redis or
# the upstream proxy when scaling out.
BUCKET_CAPACITY = 60
REFILL_PER_SECOND = 1.0
MAX_TRACKED_IPS = 10_000

_buckets: dict[str, tuple[float, float]] = {}
_buckets_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


def _allow(ip: str) -> bool:
    now = time.monotonic()
    with _buckets_lock:
        # Rotating-IP floods would otherwise grow this dict without bound.
        if len(_buckets) > MAX_TRACKED_IPS:
            _buckets.clear()

        tokens, last_seen = _buckets.get(ip, (float(BUCKET_CAPACITY), now))
        tokens = min(BUCKET_CAPACITY, tokens + (now - last_seen) * REFILL_PER_SECOND)

        if tokens < 1.0:
            _buckets[ip] = (tokens, now)
            return False

        _buckets[ip] = (tokens - 1.0, now)
        return True


def _sanitise(text: str) -> str:
    """CloudWatch splits on newlines, so an embedded one would forge an event."""
    return text.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def _valid_level(level: str) -> str:
    resolved = (level or "").strip().upper()
    if resolved not in VALID_LEVELS:
        return "INFO"
    return "WARNING" if resolved == "WARN" else resolved


def _logger_name(name: str | None) -> str:
    """Used only as a JSON field, never passed to logging.getLogger()."""
    if not name:
        return FRONTEND_LOGGER_NAME
    cleaned = "".join(c for c in name if c.isalnum() or c in "._-")[:120]
    return f"{FRONTEND_LOGGER_NAME}.{cleaned}" if cleaned else FRONTEND_LOGGER_NAME


def _clamp_context(context: dict | None) -> dict | None:
    if not context:
        return None
    return dict(list(context.items())[:MAX_CONTEXT_KEYS])


@router.post(
    "/logs",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Ingest browser logs",
    description=(
        "Accepts a batch of frontend log events and re-emits them through the "
        f"backend logger. Maximum {MAX_EVENTS_PER_BATCH} events per request."
    ),
)
async def ingest_logs(events: list[LogEventIn], request: Request) -> None:
    if not _allow(_client_ip(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many log events; try again later.",
        )

    if len(events) > MAX_EVENTS_PER_BATCH:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Maximum {MAX_EVENTS_PER_BATCH} events per request.",
        )

    for event in events:
        level = _valid_level(event.level)

        # service/env are stamped server-side, never taken from the client.
        extra: dict = {
            "service": FRONTEND_SERVICE,
            "logger_name": _logger_name(event.logger),
        }

        if event.timestamp:
            extra["timestamp"] = _sanitise(event.timestamp)
        if event.trace_id:
            extra["trace_id"] = event.trace_id
        if event.session_id:
            extra["session_id"] = event.session_id
        if event.event:
            extra["event"] = _sanitise(event.event)
        if event.duration_ms is not None:
            extra["duration_ms"] = round(event.duration_ms, 2)
        if event.error is not None:
            extra["error"] = {
                "type": _sanitise(event.error.type or ""),
                "message": _sanitise(event.error.message or ""),
                "stack": _sanitise(event.error.stack or ""),
            }

        context = _clamp_context(event.context)
        if context:
            extra["context"] = context

        frontend_logger.log(
            logging.getLevelName(level),
            _sanitise(event.message or "(no message)"),
            extra=extra,
        )
