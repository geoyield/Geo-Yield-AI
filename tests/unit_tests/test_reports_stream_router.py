"""
==============================================================================
UNIT TESTS: AI AGENT STREAMING ROUTER (SSE)
==============================================================================
File: tests/unit_tests/test_reports_stream_router.py

Tests the Server-Sent Events (SSE) streaming endpoint (`POST /api/reports/stream`).
Validates that:
1. The endpoint correctly formats events according to the W3C SSE standard.
2. The Database Session remains open throughout the entire LLM generation process.
3. Database `Decimal` types (from PostgreSQL) are correctly serialized into JSON.
"""

from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.api import app
from backend.api.deps import get_session


class FakeSessionQueRegistraCierre:
    """
    Sentinel Mock Object: 
    Registers if the Database Session was closed prematurely. In generator-based 
    streaming APIs, a common bug is the session closing after the first yield, 
    crashing the system mid-stream.
    """

    def __init__(self):
        self.cerrada = False

    def close(self):
        self.cerrada = True


def fake_get_session():
    session = FakeSessionQueRegistraCierre()
    yield session
    session.close()


def eventos_de_prueba(session, codi_districte, zona_pgm, **kwargs):
    """Mocks the LLM Agent yielding partial events over time."""
    yield {"type": "datos", "datos_distrito": {"nom_districte": "Ciutat Vella"}, "respuesta_legal": "x", "articulos_citados": ["302"]}
    assert not session.cerrada, "la sesión se cerró antes de terminar el streaming"
    yield {"type": "token", "text": "VERDE"}
    assert not session.cerrada, "la sesión se cerró antes de terminar el streaming"
    yield {"type": "done", "semaforo": "verde", "resumen": "resumen de prueba"}


def eventos_con_decimal_real(session, codi_districte, zona_pgm, **kwargs):
    """
    Regression Mock: 
    Simulates raw data coming directly from a PostgreSQL `Numeric` column. 
    SQLAlchemy maps Postgres Numerics to Python `Decimal` objects, which are 
    NOT natively JSON serializable.
    """
    yield {
        "type": "datos",
        "datos_distrito": {
            "nom_districte": "Ciutat Vella",
            "renta_media": Decimal("13990.00"),
            "daily_foot_traffic": Decimal("374030.93"),
            "opportunity_score": Decimal("11.63"),
        },
        "respuesta_legal": "x",
        "articulos_citados": ["302"],
    }
    yield {"type": "done", "semaforo": "ambar", "resumen": "resumen de prueba"}


class TestCrearInformeStream:
    def test_returns_sse_events_in_order(self):
        """Verifies the endpoint formats the output as valid W3C Server-Sent Events."""
        app.dependency_overrides[get_session] = fake_get_session
        with patch("backend.api.routers.reports.generar_informe_viabilidad_stream", side_effect=eventos_de_prueba):
            client = TestClient(app)
            with client.stream(
                "POST", "/api/reports/stream", json={"codi_districte": 1, "zona_pgm": "nucli_antic"}
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                cuerpo = "".join(response.iter_text())
        app.dependency_overrides.clear()

        lineas_datos = [l for l in cuerpo.split("\n\n") if l.startswith("data: ")]
        assert len(lineas_datos) == 3
        assert '"type": "datos"' in lineas_datos[0]
        assert '"type": "token"' in lineas_datos[1]
        assert '"type": "done"' in lineas_datos[2]

    def test_regression_session_stays_open_for_the_whole_stream(self):
        """
        Regression: Validates that FastAPI's dependency injection does not 
        close the DB session when the generator yields its first chunk.
        """
        app.dependency_overrides[get_session] = fake_get_session
        with patch("backend.api.routers.reports.generar_informe_viabilidad_stream", side_effect=eventos_de_prueba):
            client = TestClient(app)
            with client.stream(
                "POST", "/api/reports/stream", json={"codi_districte": 1, "zona_pgm": "nucli_antic"}
            ) as response:
                list(response.iter_text())  # consume el stream completo
        app.dependency_overrides.clear()

    def test_regression_decimal_fields_from_postgres_are_serializable(self):
        """
        Regression: Proves that the custom `_json_default` serializer in the 
        router successfully intercepts `Decimal` objects and casts them to floats 
        before `json.dumps` throws a TypeError.
        """
        app.dependency_overrides[get_session] = fake_get_session
        with patch(
            "backend.api.routers.reports.generar_informe_viabilidad_stream", side_effect=eventos_con_decimal_real
        ):
            client = TestClient(app)
            with client.stream(
                "POST", "/api/reports/stream", json={"codi_districte": 1, "zona_pgm": "nucli_antic"}
            ) as response:
                assert response.status_code == 200
                cuerpo = "".join(response.iter_text())
        app.dependency_overrides.clear()

        assert '"renta_media": 13990.0' in cuerpo
        assert '"opportunity_score": 11.63' in cuerpo