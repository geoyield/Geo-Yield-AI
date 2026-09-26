"""
==============================================================================
PYTEST CONFIGURATION & SHARED FIXTURES
==============================================================================
File: tests/conftest.py

This module contains Pytest fixtures that are automatically available to all 
tests in the project without explicit imports. It manages the database 
connections for integration testing and implements critical safety checks.
"""

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.db.connection import resolve_database_url

load_dotenv()


@pytest.fixture(scope="session")
def db_engine():
    try:
        url = resolve_database_url()
    except RuntimeError:
        # Graceful degradation for CI/CD pipelines without a database
        pytest.skip("DATABASE_URL no definida: se omiten los tests que necesitan una base de datos real.")

    # -------------------------------------------------------------------------
    # PRODUCTION SAFEGUARD (Bug Fix Log)
    # -------------------------------------------------------------------------
    # Critical Lesson: During early development, running the test suite accidentally 
    # deleted (truncated) the real 'legal_chunks' from the production database 
    # because my local .env file was pointing to production instead of local testing.
    # To prevent this disaster, this safeguard checks if the word 'test' is in the URL.
    # If it's not a test database, it skips the tests to prevent data loss.
    if "test" not in url.lower():
        pytest.skip(
            "DATABASE_URL does not appear to point to a test database "
            "(the name does not contain the word 'test'). "
            "These tests use TRUNCATE TABLE between executions. To prevent "
            "the destruction of real data, these tests are skipped until "
            "DATABASE_URL points to a dedicated test DB (e.g., 'geoyield_test')."
        )

    engine = create_engine(url, future=True)
    try:
        # Verify the connection actually works before returning the engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Could not connect to the database ({exc}); skipping integration tests.")
    return engine


@pytest.fixture
def db_session(db_engine):
    """
    Provides a clean SQLAlchemy Session for a single test.
    
    Test Isolation Pattern:
    It TRUNCATES the 'legal_chunks' table before AND after the test runs. 
    This ensures that each test starts with a completely blank slate and 
    does not leave garbage data behind for the next test.
    """
    session = Session(db_engine)

    # Setup: Clean slate before the test
    session.execute(text("TRUNCATE TABLE legal_chunks"))
    session.commit()

    # Yield hands control over to the actual test function
    yield session

    # Teardown: Clean up after the test completes (or fails)
    session.rollback()
    session.execute(text("TRUNCATE TABLE legal_chunks"))
    session.commit()
    session.close()