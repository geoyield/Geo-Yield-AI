"""
Tests del router de competidores (backend/api/routers/competidores.py).

Usa dependency_overrides para sustituir get_session -- sin BD real.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.api.api import app
from backend.api.deps import get_session


class FakeSessionConDatos:
    """Simula las dos consultas del endpoint: centroide+total, y el listado."""

    def __init__(self, centro_row, filas):
        self._centro_row = centro_row
        self._filas = filas

    def execute(self, statement, params=None):
        result = MagicMock()
        sql = str(statement)
        if "AVG(" in sql:
            result.mappings.return_value.first.return_value = self._centro_row
        else:
            result.mappings.return_value.all.return_value = self._filas
        return result


class TestListarCompetidores:
    def test_returns_centro_and_competidores(self):
        centro_row = {"lat": 41.38, "lng": 2.17, "total": 2}
        filas = [
            {"id_global": "a1", "nom_activitat": "Bar", "lat": 41.379, "lng": 2.171},
            {"id_global": "a2", "nom_activitat": "Restaurant", "lat": 41.381, "lng": 2.169},
        ]
        app.dependency_overrides[get_session] = lambda: FakeSessionConDatos(centro_row, filas)
        client = TestClient(app)
        response = client.get("/api/competidores", params={"codi_districte": 1})
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert body["centro"] == {"lat": 41.38, "lng": 2.17}
        assert len(body["competidores"]) == 2

    def test_regression_empty_district_returns_null_centro_not_error(self):
        # Regresión: un distrito sin competidores no debe reventar con un
        # AVG(NULL) mal manejado -- debe devolver centro=None y lista vacía.
        centro_row = {"lat": None, "lng": None, "total": 0}
        app.dependency_overrides[get_session] = lambda: FakeSessionConDatos(centro_row, [])
        client = TestClient(app)
        response = client.get("/api/competidores", params={"codi_districte": 5})
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["centro"] is None
        assert body["total"] == 0
        assert body["competidores"] == []

    def test_invalid_codi_districte_returns_422(self):
        app.dependency_overrides[get_session] = lambda: FakeSessionConDatos({"lat": None, "lng": None, "total": 0}, [])
        client = TestClient(app)
        response = client.get("/api/competidores", params={"codi_districte": 99})
        app.dependency_overrides.clear()
        assert response.status_code == 422


class FakeSessionRadio:
    """Simula las dos consultas del modo radio: COUNT total, y el listado."""

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
        fake_session = FakeSessionRadio(total=3, filas=[{"id_global": "a1", "nom_activitat": "Bar", "lat": 41.38, "lng": 2.17}])
        app.dependency_overrides[get_session] = lambda: fake_session
        client = TestClient(app)
        response = client.get(
            "/api/competidores", params={"codi_districte": 1, "lat": 41.38, "lon": 2.17, "radio_metros": 500}
        )
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["modo"] == "radio"
        assert body["radio_metros"] == 500
        assert body["centro"] == {"lat": 41.38, "lng": 2.17}  # el centro es el punto dado, no un promedio
        assert body["total"] == 3

    def test_regression_radio_count_independent_of_district_total(self):
        # Regresión: el total en modo radio debe venir de ST_DWithin
        # (competidores reales cerca del punto), no del total del
        # distrito completo -- son números distintos a propósito.
        fake_session = FakeSessionRadio(total=12, filas=[])
        app.dependency_overrides[get_session] = lambda: fake_session
        client = TestClient(app)
        response = client.get("/api/competidores", params={"codi_districte": 1, "lat": 41.38, "lon": 2.17})
        app.dependency_overrides.clear()

        assert response.json()["total"] == 12

    def test_default_district_mode_when_no_lat_lon(self):
        centro_row = {"lat": 41.38, "lng": 2.17, "total": 1588}
        app.dependency_overrides[get_session] = lambda: FakeSessionConDatos(centro_row, [])
        client = TestClient(app)
        response = client.get("/api/competidores", params={"codi_districte": 1})
        app.dependency_overrides.clear()

        assert response.json()["modo"] == "distrito"
        assert response.json()["radio_metros"] is None