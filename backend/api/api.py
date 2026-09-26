"""
==============================================================================
API APPLICATION FACTORY
==============================================================================
File: backend/api/api.py

This module defines the central instance of the FastAPI application. It acts as
the main orchestrator that consolidates:
1. Application Lifecycle Management (Lifespan).
2. Middlewares (CORS, Observability/Logging).
3. Modular Routing (Routers) segmented by business domains.
4. Health check endpoints (Liveness and Readiness probes) for orchestrators like Docker/K8s.
"""

import logging
import os
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from backend.observability import (
    configure_logging,
    get_logger,
    log_event,
    new_trace_id,
    reset_trace_id,
    set_trace_id,
)

from . import deps
from .metrics.metrics import metrics
from .routers import articles, chat, competitors, geocoding, logs, reports

# Also configured here, not only in main.py, so `uvicorn backend.api.api:app`
# is covered. Idempotent.
configure_logging()

logger = get_logger("api")

# Application Instantiation. We use the 'lifespan' pattern (context manager)
# recommended by recent FastAPI versions, deprecating the old 'startup'/'shutdown'
# events. This ensures safe database connection pooling management.
app = FastAPI(
    title="Geo-Yield-AI API",
    description="API for the hospitality premises viability AI agent.",
    lifespan=deps.lifespan,
)

# Was hardcoded to the Vite localhost ports, which made it impossible for a
# deployed frontend to call the API or ship its logs.
_DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Without this the browser cannot read the trace id back.
    expose_headers=["X-Request-ID"],
)

# Router Registration. We apply the Modular Architecture principle,
# separating business logic into distinct domains to facilitate maintainability.
app.include_router(reports.router)
app.include_router(competitors.router)
app.include_router(articles.router)
app.include_router(geocoding.router)
app.include_router(chat.router)
app.include_router(logs.router)

# Probes are called every few seconds; logging them is paid-for noise.
UNLOGGED_PATHS = frozenset({"/health", "/ready", "/metrics"})


@app.get("/health", tags=["Monitoring"])
def health() -> dict:
    """
    Liveness Probe Endpoint.

    Informs the orchestrator (e.g., Docker, Kubernetes) that the web process
    is running and has not deadlocked.

    Returns:
        dict: A dictionary with the "ok" status.

    Architectural Note:
        This endpoint is intentionally agnostic to the database state.
        If the DB goes down, the container should NOT enter a crash-loop;
        it must stay alive waiting for the DB to recover.
    """
    return {"status": "ok"}


@app.get("/ready", tags=["Monitoring"])
def ready():
    """
    Readiness Probe Endpoint.

    Unlike the Liveness probe, this endpoint verifies that the API is fully
    operational and capable of processing real traffic by checking the active
    connection to the PostgreSQL database.

    Returns:
        dict | PlainTextResponse: "ready" status (HTTP 200) if connected,
        or an error (HTTP 503 Service Unavailable) if the DB is unreachable.

    Python Technical Note:
        We access the `deps.db_engine` attribute dynamically. Had we used
        `from .deps import db_engine`, the initial import would have copied
        the `None` value (by value). By accessing via the module namespace,
        we guarantee reading the updated pointer managed by the Lifespan context.
    """
    if deps.db_engine is None:
        return PlainTextResponse("database not initialized", status_code=503)

    try:
        # Executes a trivial query to validate TCP communication with the DB.
        with deps.db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        logger.exception("Readiness check failed")
        return PlainTextResponse("database unreachable", status_code=503)


@app.get("/metrics", response_class=PlainTextResponse, tags=["Monitoring"])
def metrics_endpoint() -> str:
    """
    Application Metrics Endpoint.

    Exposes Key Performance Indicators (KPIs) in plain text format,
    making them ready to be scraped by external monitoring tools like Prometheus.

    Returns:
        str: Text string containing the total processed requests.
    """
    return f'total_requests {metrics["total_requests"]}\n'


@app.middleware("http")
async def track_request_count(request, call_next):
    """
    Pins the trace id and logs method, path, status and duration.

    Was a logger.debug(), which never emitted at the default LOG_LEVEL=20 --
    so in practice there was no request log at all. The trace id comes from
    the frontend's X-Request-ID header, or is generated, and is pinned in a
    ContextVar so every log line raised during this request carries it.
    """
    trace_id = request.headers.get("X-Request-ID") or new_trace_id()
    # Client-controlled and ends up in every log line, so constrain it.
    trace_id = "".join(c for c in trace_id if c.isalnum() or c in "-_")[:64] or new_trace_id()
    token = set_trace_id(trace_id)

    start = time.perf_counter()
    metrics["total_requests"] += 1

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        # One record, not two: exc_info lets the formatter build the `error`
        # object, so a separate logger.exception() would double the ingestion.
        logger.error(
            f"{request.method} {request.url.path} - unhandled exception",
            exc_info=True,
            extra={
                "duration_ms": round(duration_ms, 2),
                "context": {"method": request.method, "path": request.url.path},
            },
        )
        reset_trace_id(token)
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = trace_id

    if request.url.path not in UNLOGGED_PATHS:
        # Keeps `filter level = "ERROR"` meaningful in Logs Insights.
        if response.status_code >= 500:
            level = logging.ERROR
        elif response.status_code >= 400:
            level = logging.WARNING
        else:
            level = logging.INFO

        log_event(
            logger,
            level,
            f"{request.method} {request.url.path} {response.status_code}",
            duration_ms=duration_ms,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )

    reset_trace_id(token)
    return response