import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from . import deps
from .metrics.metrics import metrics
from .routers import articulos, chat, competidores, geocodificacion, informes

# El logging global se configura en main.py (punto de entrada). Aquí solo se
# obtiene el logger ya configurado, para mantener un único punto de control
# del nivel de log (variable de entorno LOG_LEVEL).
logger = logging.getLogger("geoyield_api")

app = FastAPI(
    title="Geo-Yield-AI API",
    description="API del agente de viabilidad de locales de hostelería.",
    lifespan=deps.lifespan,
)

# CORS para el servidor de desarrollo de Vite (puertos por defecto). En
# producción, restringir a los dominios reales del frontend desplegado,
# no dejar esta lista de orígenes permisivos.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(informes.router)
app.include_router(competidores.router)
app.include_router(articulos.router)
app.include_router(geocodificacion.router)
app.include_router(chat.router)


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
    except Exception as exc:
        logger.error(f"Readiness check falló: {exc}")
        return PlainTextResponse("database unreachable", status_code=503)


@app.get("/metrics", response_class=PlainTextResponse)
def metrics_endpoint():
    return f'total_requests {metrics["total_requests"]}\n'


@app.middleware("http")
async def track_request_count(request, call_next):
    """Middleware mínimo de observabilidad: cuenta peticiones y su duración."""
    start = time.time()
    metrics["total_requests"] += 1
    response = await call_next(request)
    duration = time.time() - start
    logger.debug(f"{request.method} {request.url.path} - {duration:.3f}s")
    return response