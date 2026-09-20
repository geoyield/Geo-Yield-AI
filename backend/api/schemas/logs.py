"""
Schema for log events sent by the browser; server side of the contract in
frontend/src/services/logger.js.

`extra="ignore"` rather than the `extra="forbid"` used by the other schemas
here: after a deploy some browsers still run the previous frontend, and
rejecting their batch over one unknown key would drop the logs that matter most.
"""

from pydantic import BaseModel, ConfigDict, Field

# "WARN" is accepted as an alias because the JS method is console.warn.
VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "WARN", "ERROR", "CRITICAL"}

# Public and unauthenticated, so these caps guard against cost amplification.
MAX_EVENTS_PER_BATCH = 100
MAX_CONTEXT_KEYS = 30


class ErrorIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str | None = Field(default=None, max_length=200)
    message: str | None = Field(default=None, max_length=4_000)
    stack: str | None = Field(default=None, max_length=8_000)


class LogEventIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # When it happened in the browser, not when the batch arrived.
    timestamp: str | None = Field(default=None, max_length=40)
    level: str = Field(default="INFO", max_length=20)
    logger: str | None = Field(default=None, max_length=120)
    message: str = Field(default="", max_length=16_000)
    trace_id: str | None = Field(default=None, max_length=64)
    session_id: str | None = Field(default=None, max_length=64)
    event: str | None = Field(default=None, max_length=120)
    duration_ms: float | None = None
    error: ErrorIn | None = None
    context: dict | None = None

    # Note what is absent: service, env and version. The server stamps those,
    # otherwise a client could impersonate the API.
