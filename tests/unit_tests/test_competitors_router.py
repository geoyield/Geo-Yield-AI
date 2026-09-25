"""
==============================================================================
UNIT TESTS: COMPETITORS ROUTER
==============================================================================
File: tests/unit_tests/test_competitors_router.py

Tests the API endpoints defined in `backend/api/routers/competitors.py`.
Uses FastAPI's dependency injection overrides to mock the database session, 
ensuring tests run quickly without a real PostgreSQL connection.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.api.api import app
from backend.api.deps import get_session


class FakeSessionConDatos:
    """
    Mock class that simulates a SQLAlchemy Session for the 'District Mode'.
    It intercepts SQL strings and returns hardcoded data instead of hitting 
    a real database.
    """

    def __init__(self, centro_row, filas):
        self._centro_row = centro_row
        self._filas = filas

    def execute(self, statement, params=None):
        result = MagicMock()
        sql = str(statement)
        # If the SQL contains AVG, it's asking for the centroid (first query)
        if "AVG(" in sql:
            result.mappings.return_value.first.return_value = self._centro_row
        # Otherwise, it's asking for the list of competitors (second query)    
        else:
            result.mappings.return_value.all.return_value = self._filas
        return result


class TestListarCompetidores:
    def test_returns_centro_and_competidores(self):
        """Verifies the standard behavior of the endpoint in District Mode."""
        centro_row = {"lat": 41.38, "lng": 2.17, "total": 2}
        filas = [
            {"id_global": "a1", "nom_activitat": "Bar", "lat": 41.379, "lng": 2.171},
            {"id_global": "a2", "nom_activitat": "Restaurant", "lat": 41.381, "lng": 2.169},
        ]

        # Dependency Injection: Swap the real DB session with our Mock
        app.dependency_overrides[get_session] = lambda: FakeSessionConDatos(centro_row, filas)
        client = TestClient(app)
        response = client.get("/api/competitors", params={"codi_districte": 1})
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert body["centro"] == {"lat": 41.38, "lng": 2.17}
        assert len(body["competidores"]) == 2

    def test_regression_empty_district_returns_null_centro_not_error(self):
        """
        Regression Test: If a district has 0 competitors, SQL's AVG() returns NULL. 
        The API must handle this gracefully and return `null` in JSON, not a 500 Server Error.
        """
        centro_row = {"lat": None, "lng": None, "total": 0}
        app.dependency_overrides[get_session] = lambda: FakeSessionConDatos(centro_row, [])
        client = TestClient(app)
        response = client.get("/api/competitors", params={"codi_districte": 5})
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["centro"] is None
        assert body["total"] == 0
        assert body["competidores"] == []

    def test_invalid_codi_districte_returns_422(self):
        """Pydantic validation: Ensure district codes outside 1-10 are rejected."""
        app.dependency_overrides[get_session] = lambda: FakeSessionConDatos({"lat": None, "lng": None, "total": 0}, [])
        client = TestClient(app)
        # 99 is not a valid Barcelona district
        response = client.get("/api/competitors", params={"codi_districte": 99})
        app.dependency_overrides.clear()

        # 422 Unprocessable Entity (FastAPI standard validation error)
        assert response.status_code == 422


class FakeSessionRadio:
    """Mock class simulating the 'Radius Mode' queries (ST_DWithin)."""

    def __init__(self, total, filas):
        self._total = total
        self._filas = filas
        self.ultimos_params = None

    def execute(self, statement, params=None):
        self.ultimos_params = params
        result = MagicMock()
        sql = str(statement)
        if "COUNT(*)" in sql:
            result.mappings.return_value.first.return_value = {"total": self._total}
        else:
            result.mappings.return_value.all.return_value = self._filas
        return result


class TestListarCompetidoresPorRadio:
    def test_uses_radio_mode_when_lat_lon_given(self):
        """Verifies that providing Lat/Lon automatically switches the API mode."""
        fake_session = FakeSessionRadio(total=3, filas=[{"id_global": "a1", "nom_activitat": "Bar", "lat": 41.38, "lng": 2.17}])
        app.dependency_overrides[get_session] = lambda: fake_session
        client = TestClient(app)
        response = client.get(
            "/api/competitors", params={"codi_districte": 1, "lat": 41.38, "lon": 2.17, "radio_metros": 500}
        )
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["modo"] == "radio"
        assert body["radio_metros"] == 500
        # In radius mode, the center must be the exact point provided, not an average
        assert body["centro"] == {"lat": 41.38, "lng": 2.17}  
        assert body["total"] == 3

    def test_regression_radio_count_independent_of_district_total(self):
        """
        Regression Test: The total count in radius mode must come from the 
        spatial query (ST_DWithin), NOT from the total district size.
        """
        fake_session = FakeSessionRadio(total=12, filas=[])
        app.dependency_overrides[get_session] = lambda: fake_session
        client = TestClient(app)
        response = client.get("/api/competitors", params={"codi_districte": 1, "lat": 41.38, "lon": 2.17})
        app.dependency_overrides.clear()

        assert response.json()["total"] == 12

    def test_default_district_mode_when_no_lat_lon(self):
        """Verifies the default fallback when coordinates are missing."""
        centro_row = {"lat": 41.38, "lng": 2.17, "total": 1588}
        app.dependency_overrides[get_session] = lambda: FakeSessionConDatos(centro_row, [])
        client = TestClient(app)
        response = client.get("/api/competitors", params={"codi_districte": 1})
        app.dependency_overrides.clear()

        assert response.json()["modo"] == "distrito"
        assert response.json()["radio_metros"] is None