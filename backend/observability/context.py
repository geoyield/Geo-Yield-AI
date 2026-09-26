"""Per-request context propagated to every log record."""

import uuid
from contextvars import ContextVar, Token

# A ContextVar, not a global: FastAPI serves concurrent requests on one
# asyncio loop, so a global would leak between overlapping requests.
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def get_trace_id() -> str | None:
    return _trace_id.get()


def set_trace_id(trace_id: str) -> Token:
    """Returns a token for `reset_trace_id()`."""
    return _trace_id.set(trace_id)


def reset_trace_id(token: Token) -> None:
    _trace_id.reset(token)
