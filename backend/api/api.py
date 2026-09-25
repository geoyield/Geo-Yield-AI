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
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from . import deps
from .metrics.metrics import metrics
from .routers import articles, chat, competitors, geocoding, reports

# Loose Coupling Principle in Logging:
# In this file (api.py), we strictly limit ourselves to "requesting" the logger 
# named "geoyield_api" to emit messages. The responsibility of deciding HOW and 
# WHERE these messages are stored (console vs .log file, formatting) is centralized 
# in main.py. Thus, if we change the logging storage strategy in the future, 
# not a single line of business logic in this API needs to be modified.
logger = logging.getLogger("geoyield_api")

# Application Instantiation. We use the 'lifespan' pattern (context manager) 
# recommended by recent FastAPI versions, deprecating the old 'startup'/'shutdown' 
# events. This ensures safe database connection pooling management.
app = FastAPI(
    title="Geo-Yield-AI API",
    description="API for the hospitality premises viability AI agent.",
    lifespan=deps.lifespan,
)

# CORS (Cross-Origin Resource Sharing) Middleware Configuration.
# Allows the client (Vue/Vite Frontend) hosted on different domains/ports 
# to consume this API without being blocked by the browser's Same-Origin Policy (SOP).
# NOTE: In a strict production environment, this list must be restricted 
# exclusively to the final domain URL, avoiding permissive origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router Registration. We apply the Modular Architecture principle, 
# separating business logic into distinct domains to facilitate maintainability.
app.include_router(reports.router)
app.include_router(competitors.router)
app.include_router(articles.router)
app.include_router(geocoding.router)
app.include_router(chat.router)


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
    except Exception as exc:
        logger.error(f"Readiness check failed: {exc}")
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
    Observability and Request Interception Middleware.
    
    Acts as a proxy wrapping every incoming HTTP request. Its purpose 
    is code instrumentation:
    1. Increments the global metrics counter.
    2. Calculates the processing time (latency) of each endpoint.
    3. Logs the trace in the logging system to facilitate debugging.
    
    Args:
        request (Request): The incoming HTTP request object.
        call_next (Callable): The function passing control to the next middleware/route.
        
    Returns:
        Response: The HTTP response generated by the backend.
    """
    start = time.time()
    
    # 1. Metric Registration
    metrics["total_requests"] += 1
    
    # 2. Pass control and await resolution
    response = await call_next(request)
    
    # 3. Performance calculation and traceability logging
    duration = time.time() - start
    logger.debug(f"{request.method} {request.url.path} - {duration:.3f}s")
    
    return response