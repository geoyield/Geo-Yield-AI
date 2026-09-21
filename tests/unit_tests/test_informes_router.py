"""
Tests del router de informes (backend/api/routers/informes.py).

Usa dependency_overrides de FastAPI para sustituir get_session por un doble, y
parchea generar_informe_viabilidad para no depender de una base de datos
real ni de una llamada real a Gemini -- estos tests validan el cableado
HTTP (rutas, esquemas, códigos de estado), no la lógica del agente en sí
(esa ya tiene su propia suite en test_agent.py).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.api import app
from backend.api.deps import get_session


class FakeRow:
    """Imita una fila de resultado de SQLAlchemy (acceso por atributo)."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeSession:
    def __init__(self, rows=None):
        self._rows = rows or []

    def execute(self, *args, **kwargs):
        result = MagicMock()
        result.all.return_value = self._rows
        return result


@pytest.fixture
def client_con_distritos():
    fake_db = FakeSession(rows=[FakeRow(codi_districte=1, nom_districte="Ciutat Vella")])
    app.dependency_overrides[get_session] = lambda: fake_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListarDistritos:
    def test_returns_districts_from_db(self, client_con_distritos):
        response = client_con_distritos.get("/api/distritos")
        assert response.status_code == 200
        assert response.json() == [{"codi_districte": 1, "nom_districte": "Ciutat Vella"}]


class TestListarZonasPgm:
    def test_returns_zones_with_readable_names(self):
        app.dependency_overrides[get_session] = lambda: FakeSession()
        with patch("backend.api.routers.informes.zonas_pgm_disponibles", return_value=["nucli_antic"]):
            client = TestClient(app)
            response = client.get("/api/zonas-pgm")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body[0]["id"] == "nucli_antic"
        assert "Nucli antic" in body[0]["nombre"]


class TestCrearInforme:
    def test_returns_informe_on_success(self):
        app.dependency_overrides[get_session] = lambda: FakeSession()
        informe_falso = {
            "semaforo": "verde",
            "resumen": "Resumen de prueba.",
            "datos_distrito": {"codi_districte": 1, "nom_districte": "Ciutat Vella", "opportunity_score": 69.67},
            "respuesta_legal": "Respuesta legal de prueba.",
            "articulos_citados": [{"numero_articulo": "302", "fuente_legal": "PGM (Secció V)"}],
        }
        with patch("backend.api.routers.informes.generar_informe_viabilidad", return_value=informe_falso):
            client = TestClient(app)
            response = client.post("/api/informes", json={"codi_districte": 1, "zona_pgm": "nucli_antic"})
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["semaforo"] == "verde"

    def test_regression_llm_failure_returns_502_not_raw_traceback(self):
        # Regresión: si el LLM o la BD fallan dentro del agente, el
        # endpoint debe devolver un 502 con un mensaje claro -- no dejar
        # que la excepción se propague como un 500 con stack trace crudo
        # hacia el frontend.
        app.dependency_overrides[get_session] = lambda: FakeSession()
        with patch(
            "backend.api.routers.informes.generar_informe_viabilidad", side_effect=RuntimeError("fallo simulado")
        ):
            client = TestClient(app)
            response = client.post("/api/informes", json={"codi_districte": 1, "zona_pgm": "nucli_antic"})
        app.dependency_overrides.clear()

        assert response.status_code == 502
        assert "Inténtalo de nuevo" in response.json()["detail"]

    def test_invalid_codi_districte_returns_422(self):
        app.dependency_overrides[get_session] = lambda: FakeSession()
        client = TestClient(app)
        response = client.post("/api/informes", json={"codi_districte": 99, "zona_pgm": "nucli_antic"})
        app.dependency_overrides.clear()
        assert response.status_code == 422  # fuera del rango 1-10, lo valida Pydantic antes de tocar el agente