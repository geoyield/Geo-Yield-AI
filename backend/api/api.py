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
from .routers import articulos, competidores, geocodificacion, informes, logs

# Also configured here, not only in main.py, so `uvicorn backend.api.api:app`
# is covered. Idempotent.
configure_logging()

logger = get_logger("api")

app = FastAPI(
    title="Geo-Yield-AI API",
    description="API del agente de viabilidad de locales de hostelería.",
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

app.include_router(informes.router)
app.include_router(competidores.router)
app.include_router(articulos.router)
app.include_router(geocodificacion.router)
app.include_router(logs.router)

# Probes are called every few seconds; logging them is paid-for noise.
UNLOGGED_PATHS = frozenset({"/health", "/ready", "/metrics"})


@app.get("/health")
def health():
    """
    Liveness probe: confirma que el proceso está arriba.
    No depende de la base de datos a propósito, para que un contenedor
    orquestado (Docker/K8s) no lo reinicie en bucle si la BD está caída.
    """
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """
    Readiness probe: confirma que la aplicación puede atender tráfico real,
    es decir, que la base de datos está accesible.

    Se accede a `deps.db_engine` (atributo del módulo), no a un valor
    importado con `from .deps import db_engine`: el lifespan lo asigna en
    tiempo de ejecución, después de que este módulo ya se haya importado
    -- un `from ... import db_engine` capturaría el valor `None` que tenía
    en el momento del import y nunca vería la actualización posterior.
    """
    if deps.db_engine is None:
        return PlainTextResponse("database not initialized", status_code=503)

    try:
        with deps.db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        logger.exception("Readiness check failed")
        return PlainTextResponse("database unreachable", status_code=503)


@app.get("/metrics", response_class=PlainTextResponse)
def metrics_endpoint():
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
