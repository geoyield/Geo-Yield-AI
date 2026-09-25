"""
==============================================================================
DATABASE DEPENDENCIES & LIFECYCLE MANAGEMENT
==============================================================================
File: backend/api/deps.py

Database connection pooling and session creation logic.

Architectural Lesson:
We extracted this code from the main `api.py` file into a separate module 
to prevent a "Circular Dependency" issue. If the routers imported the session 
from `api.py`, and `api.py` in turn imported the routers to register them, 
the Python interpreter would deadlock, unable to resolve the loading order.
"""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from backend.db.connection import resolve_database_url

# We load the .env variables here in case we are running the API locally 
# (e.g., executing Uvicorn directly). If we are running inside Docker, 
# Docker already injects the environment variables, and this line safely does nothing.
load_dotenv()

logger = logging.getLogger("geoyield_api")

# Global variables to hold the database engine and session factory.
# Initialized as None so they are only populated when the application actually starts.
db_engine: Engine | None = None
SessionLocal: sessionmaker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifecycle Manager (Context Manager).
    
    Controls the execution flow during application startup and shutdown.

    During startup, we configure the PostgreSQL/PostGIS connection pool. 
    We perform a 'Fail-Fast' check: if the database is unreachable, we prefer 
    the application to crash immediately rather than starting in a degraded 
    state and throwing runtime errors to users later.
    """
    global db_engine, SessionLocal

    try:
        database_url = resolve_database_url()
    except RuntimeError:
        logger.error("Missing DATABASE_URL variable in the .env file")
        raise

    try:
        # Database Engine Creation.
        # Defensive Programming: We use pool_pre_ping=True so SQLAlchemy 
        # transparently tests the connection's health before returning it from the pool. 
        # This is critical if the database service was unexpectedly restarted.
        db_engine = create_engine(database_url, pool_pre_ping=True, future=True)
        SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        # We execute a trivial SELECT 1 to force SQLAlchemy to establish 
        # a real TCP connection right now, ensuring everything is properly configured.
        with db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successfully established.")

    except Exception as e:
        logger.error(f"Failed to connect to the database during startup: {e}")
        raise

    # The application yields control back to the event loop, 
    # running and serving HTTP requests from this point onwards.
    yield

    # Teardown phase: When the API is stopped (e.g., SIGTERM or Ctrl+C), 
    # we cleanly dispose of the connection pool to prevent memory leaks.
    if db_engine is not None:
        db_engine.dispose()
        logger.info("Database connections safely closed.")


def get_session():
    """
    Dependency Injection provider for Database Sessions.

    Intended to be used as a FastAPI dependency (`Depends(get_session)`). 
    The try...finally block is a vital safety mechanism: it guarantees that, 
    no matter what happens during the HTTP request (even if a 500 Server Error occurs), 
    the connection is always returned to the SQLAlchemy pool.
    """
    if SessionLocal is None:
        raise RuntimeError("Attempted to request a database session before initialization.")
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()