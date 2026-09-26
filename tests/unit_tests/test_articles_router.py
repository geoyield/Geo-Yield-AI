"""
==============================================================================
UNIT TESTS: LEGAL ARTICLE ROUTER
==============================================================================
File: tests/unit_tests/test_articles_router.py

Tests the FastAPI router endpoints (`backend/api/routers/articles.py`).
Uses FastAPI `dependency_overrides` to mock `get_session` -- running strictly 
without a real database to isolate the API routing logic.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.api.api import app
from backend.api.deps import get_session


class FakeSession:
    """Mock class simulating a SQLAlchemy Session."""
    def __init__(self, fila=None):
        self._fila = fila
        self.ultimos_params = None

    def execute(self, statement, params=None):
        """Spies on the execution to capture the exact SQL parameters used."""
        self.ultimos_params = params
        result = MagicMock()
        result.mappings.return_value.first.return_value = self._fila
        return result


class TestObtenerArticulo:
    def test_returns_full_article_when_found(self):
        """Verifies the GET endpoint successfully returns a mocked DB row."""
        fila = {
            "fuente_legal": "PGM (Secció V)",
            "numero_articulo": "302",
            "titulo": "Zona de nucli antic",
            "contenido": "Texto completo del artículo 302.",
        }
        app.dependency_overrides[get_session] = lambda: FakeSession(fila)
        client = TestClient(app)
        response = client.get("/api/articles", params={"fuente_legal": "PGM (Secció V)", "numero_articulo": "302"})
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json() == fila

    def test_regression_source_with_special_characters_in_query_param(self):
        """
        Regression Test (URL Encoding):
        Proves the architectural decision made in Phase 4. Legal sources like 
        'Ley 22/2010 (Código de Consumo de Cataluña)' contain slashes and parentheses. 
        This test confirms that passing them as Query Parameters correctly 
        handles URL-encoding without breaking the FastAPI router (which would 
        happen if they were Path Parameters).
        """
        fila = {
            "fuente_legal": "Ley 22/2010 (Código de Consumo de Cataluña)",
            "numero_articulo": "111-1",
            "titulo": "Objeto y ámbito",
            "contenido": "Texto de prueba.",
        }
        app.dependency_overrides[get_session] = lambda: FakeSession(fila)
        client = TestClient(app)
        response = client.get(
            "/api/articles",
            params={"fuente_legal": "Ley 22/2010 (Código de Consumo de Cataluña)", "numero_articulo": "111-1"},
        )
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["fuente_legal"] == "Ley 22/2010 (Código de Consumo de Cataluña)"

    def test_returns_404_when_article_not_found(self):
        """Verifies proper HTTP 404 handling when the DB returns None."""
        app.dependency_overrides[get_session] = lambda: FakeSession(None)
        client = TestClient(app)
        response = client.get("/api/articles", params={"fuente_legal": "No existe", "numero_articulo": "1"})
        app.dependency_overrides.clear()

        assert response.status_code == 404

    def test_regression_whitespace_only_value_returns_422_not_a_db_lookup(self):
        """
        Regression Test (Input Validation Edge Case):
        Pydantic's `Query(..., min_length=1)` only validates the string length 
        BEFORE whitespace stripping. A value of " " (one space) passes Pydantic. 
        If the router calls `.strip()` without checking again, it passes an 
        empty string to the DB, causing a silent failure. 
        This test ensures the code catches this edge case and explicitly 
        throws an HTTP 422 Unprocessable Entity.
        """
        app.dependency_overrides[get_session] = lambda: FakeSession(None)
        client = TestClient(app)
        response = client.get("/api/articles", params={"fuente_legal": " ", "numero_articulo": "302"})
        app.dependency_overrides.clear()

        assert response.status_code == 422
        assert "no pueden estar vacíos" in response.json()["detail"]

    def test_regression_leading_trailing_whitespace_is_stripped_before_lookup(self):
        """
        Regression Test (Input Sanitization Validation):
        Uses the FakeSession as a 'Spy' to verify that the router calls `.strip()` 
        and cleans accidental user input (e.g., from a copy-paste) BEFORE passing 
        it to the SQL engine. 
        It asserts against `fake_session.ultimos_params`, not just the HTTP status.
        """
        fila = {
            "fuente_legal": "PGM (Secció V)",
            "numero_articulo": "302",
            "titulo": "Zona de nucli antic",
            "contenido": "Texto completo.",
        }
        fake_session = FakeSession(fila)
        app.dependency_overrides[get_session] = lambda: fake_session
        client = TestClient(app)
        response = client.get(
            "/api/articles", params={"fuente_legal": "  PGM (Secció V)  ", "numero_articulo": " 302 "}
        )
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert fake_session.ultimos_params == {"fuente": "PGM (Secció V)", "numero": "302"}