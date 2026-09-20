"""
Gestión del ciclo de vida de la conexión a base de datos y la dependencia
de sesión para los endpoints.

Extraído de api.py a un módulo aparte (sin cambios de lógica) para que los
routers de dominio (backend/api/routers/*) puedan importar `get_session`
sin crear un import circular con api.py -- si el router importara
`get_session` directamente desde api.py, y api.py importara el router
para registrarlo, cada uno esperaría al otro al cargar.
"""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from backend.db.connection import resolve_database_url
from backend.observability import get_logger, shutdown_logging, tame_third_party_loggers

# Se carga aquí, a nivel de módulo, para cubrir el caso de correr uvicorn
# directamente en la máquina (sin pasar por Docker, donde env_file en
# docker-compose.yml ya inyecta las variables por su cuenta). load_dotenv()
# no sobreescribe variables ya presentes en el entorno por defecto, así que
# no interfiere con el caso de Docker.
load_dotenv()

logger = get_logger("api.deps")

# Estado de aplicación gestionado por el lifespan. Se evita usar variables
# globales mutables fuera de este patrón para no acoplar el estado a nivel
# de módulo con la lógica de negocio futura.
db_engine: Engine | None = None
SessionLocal: sessionmaker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Ciclo de vida de la aplicación.

    Al arrancar: crea el engine de SQLAlchemy contra Postgres/PostGIS.
    Se falla rápido (fail-fast) si la variable DATABASE_URL no está definida
    o la base de datos no es accesible, para no servir tráfico con un estado
    inconsistente.
    """
    global db_engine, SessionLocal

    # Re-applied here because a CLI start installs uvicorn's own logging
    # config after this module is imported; the lifespan runs after that.
    tame_third_party_loggers()

    try:
        database_url = resolve_database_url()
    except RuntimeError:
        logger.error("DATABASE_URL no está definida en el entorno.")
        raise

    try:
        # pool_pre_ping evita servir conexiones muertas del pool (p. ej. tras
        # un reinicio de la base de datos) haciendo un ping ligero antes de
        # reutilizar cada conexión.
        db_engine = create_engine(database_url, pool_pre_ping=True, future=True)
        SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        # Verificación de conectividad real en el arranque, no solo de que
        # el engine se haya podido instanciar (create_engine es perezoso y
        # no abre conexión por sí solo).
        with db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Conexión a la base de datos establecida correctamente.")

    except Exception:
        logger.exception("Fallo al inicializar la conexión a la base de datos.")
        raise

    yield

    if db_engine is not None:
        db_engine.dispose()
        logger.info("Conexiones a la base de datos cerradas.")

    # Drains the pending CloudWatch queue before the process exits.
    shutdown_logging()


def get_session():
    """
    Crea una sesión de base de datos.

    Debe llamarse únicamente después de que el lifespan haya inicializado
    SessionLocal. Pensada para usarse como dependencia de FastAPI
    (`Depends(get_session)`) en los endpoints de dominio.
    """
    if SessionLocal is None:
        raise RuntimeError("La base de datos no se ha inicializado todavía.")
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()