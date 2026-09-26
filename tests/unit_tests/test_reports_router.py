"""
==============================================================================
UNIT TESTS: ORCHESTRATOR API ROUTER
==============================================================================
File: tests/unit_tests/test_informes_router.py

Tests the FastAPI router endpoints (`backend/api/routers/informes.py`).
It uses FastAPI `dependency_overrides` to mock the database and `patch` to 
mock the LangGraph Agent. 

Architectural Note (Separation of Concerns):
These tests DO NOT validate the AI Agent logic (that is handled by `test_agent.py`). 
These tests exclusively validate the HTTP Wiring (routes, Pydantic schemas, 
and HTTP Status Codes).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.api import app
from backend.api.deps import get_session


class FakeRow:
    """Mock class simulating a SQLAlchemy row result (attribute access)."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeSession:
    """Mock class simulating a SQLAlchemy Session."""
    def __init__(self, rows=None):
        self._rows = rows or []

    def execute(self, *args, **kwargs):
        result = MagicMock()
        result.all.return_value = self._rows
        return result


@pytest.fixture
def client_con_distritos():
    """Dependency Injection: Replaces the Postgres session with a fake DB."""
    fake_db = FakeSession(rows=[FakeRow(codi_districte=1, nom_districte="Ciutat Vella")])
    app.dependency_overrides[get_session] = lambda: fake_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListarDistritos:
    def test_returns_districts_from_db(self, client_con_distritos):
        """Verifies the GET /distritos endpoint returns correctly formatted JSON."""
        response = client_con_distritos.get("/api/districts")
        assert response.status_code == 200
        assert response.json() == [{"codi_districte": 1, "nom_districte": "Ciutat Vella"}]


class TestListarZonasPgm:
    def test_returns_zones_with_readable_names(self):
        """Verifies that dynamic zones are fetched and mapped to readable names."""
        app.dependency_overrides[get_session] = lambda: FakeSession()
        with patch("backend.api.routers.reports.zonas_pgm_disponibles", return_value=["nucli_antic"]):
            client = TestClient(app)
            response = client.get("/api/pgm-zones")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body[0]["id"] == "nucli_antic"
        assert "Nucli antic" in body[0]["nombre"]


class TestCrearInforme:
    def test_returns_informe_on_success(self):
        """
        Boundary Testing:
        Mocks `generar_informe_viabilidad` to return a predefined dictionary. 
        This proves the API correctly converts the Agent's raw output into the 
        strict Pydantic `InformeResponse` format.
        """
        app.dependency_overrides[get_session] = lambda: FakeSession()
        informe_falso = {
            "semaforo": "verde",
            "resumen": "Resumen de prueba.",
            "datos_distrito": {"codi_districte": 1, "nom_districte": "Ciutat Vella", "opportunity_score": 69.67},
            "respuesta_legal": "Respuesta legal de prueba.",
            "articulos_citados": [{"numero_articulo": "302", "fuente_legal": "PGM (Secció V)"}],
        }
        with patch("backend.api.routers.reports.generar_informe_viabilidad", return_value=informe_falso):
            client = TestClient(app)
            response = client.post("/api/reports", json={"codi_districte": 1, "zona_pgm": "nucli_antic"})
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["semaforo"] == "verde"

    def test_regression_llm_failure_returns_502_not_raw_traceback(self):
        """
        Security Regression Test:
        If the LangGraph Agent or the Gemini API crash (RuntimeError), the API 
        MUST catch it and return a clean HTTP 502 Bad Gateway. 
        It must never leak the raw Python Stack Trace to the client.
        """
        app.dependency_overrides[get_session] = lambda: FakeSession()
        with patch(
            "backend.api.routers.reports.generar_informe_viabilidad", side_effect=RuntimeError("fallo simulado")
        ):
            client = TestClient(app)
            response = client.post("/api/reports", json={"codi_districte": 1, "zona_pgm": "nucli_antic"})
        app.dependency_overrides.clear()

        assert response.status_code == 502
        assert "Please try again" in response.json()["detail"]

    def test_invalid_codi_districte_returns_422(self):
        """
        Validation Test:
        Verifies Pydantic blocks invalid inputs (District 99) with an HTTP 422 
        before the request even reaches the Agent logic.
        """
        app.dependency_overrides[get_session] = lambda: FakeSession()
        client = TestClient(app)
        response = client.post("/api/reports", json={"codi_districte": 99, "zona_pgm": "nucli_antic"})
        app.dependency_overrides.clear()

        # 422 Unprocessable Entity
        assert response.status_code == 422 