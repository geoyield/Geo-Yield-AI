"""
Test adicional del router de informes: el endpoint de streaming
(POST /api/informes/stream). Confirma el formato Server-Sent Events, que
la sesión de BD permanece abierta durante todo el streaming, y que los
valores Decimal que vienen de Postgres (renta_media, opportunity_score...)
se serializan correctamente a JSON.
"""

from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.api import app
from backend.api.deps import get_session


class FakeSessionQueRegistraCierre:
    """Session simulada que registra si se cerró antes de que el streaming terminara."""

    def __init__(self):
        self.cerrada = False

    def close(self):
        self.cerrada = True


def fake_get_session():
    session = FakeSessionQueRegistraCierre()
    yield session
    session.close()


def eventos_de_prueba(session, codi_districte, zona_pgm, **kwargs):
    yield {"type": "datos", "datos_distrito": {"nom_districte": "Ciutat Vella"}, "respuesta_legal": "x", "articulos_citados": ["302"]}
    assert not session.cerrada, "la sesión se cerró antes de terminar el streaming"
    yield {"type": "token", "text": "VERDE"}
    assert not session.cerrada, "la sesión se cerró antes de terminar el streaming"
    yield {"type": "done", "semaforo": "verde", "resumen": "resumen de prueba"}


def eventos_con_decimal_real(session, codi_districte, zona_pgm, **kwargs):
    # Regresión real: datos_distrito, tal como lo entrega generar_informe_
    # viabilidad_stream sin pasar por un esquema Pydantic, trae Decimal
    # (no float) para los campos numéricos -- exactamente lo que devuelve
    # psycopg2/SQLAlchemy al leer columnas Numeric de Postgres.
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
        app.dependency_overrides[get_session] = fake_get_session
        with patch("backend.api.routers.informes.generar_informe_viabilidad_stream", side_effect=eventos_de_prueba):
            client = TestClient(app)
            with client.stream(
                "POST", "/api/informes/stream", json={"codi_districte": 1, "zona_pgm": "nucli_antic"}
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
        # La propia función eventos_de_prueba ya comprueba esto con un
        # assert interno en cada yield -- si la sesión se cerrara antes de
        # tiempo, este test fallaría con el AssertionError de arriba en
        # vez de completar normalmente.
        app.dependency_overrides[get_session] = fake_get_session
        with patch("backend.api.routers.informes.generar_informe_viabilidad_stream", side_effect=eventos_de_prueba):
            client = TestClient(app)
            with client.stream(
                "POST", "/api/informes/stream", json={"codi_districte": 1, "zona_pgm": "nucli_antic"}
            ) as response:
                list(response.iter_text())  # consume el stream completo
        app.dependency_overrides.clear()

    def test_regression_decimal_fields_from_postgres_are_serializable(self):
        # Bug real: json.dumps no sabe serializar Decimal por defecto.
        # datos_distrito trae Decimal para los campos numéricos (viene
        # directo de Postgres, sin pasar por un esquema Pydantic que
        # los convierta a float) -- sin el 'default' en json.dumps, esto
        # revienta con TypeError a mitad del streaming.
        app.dependency_overrides[get_session] = fake_get_session
        with patch(
            "backend.api.routers.informes.generar_informe_viabilidad_stream", side_effect=eventos_con_decimal_real
        ):
            client = TestClient(app)
            with client.stream(
                "POST", "/api/informes/stream", json={"codi_districte": 1, "zona_pgm": "nucli_antic"}
            ) as response:
                assert response.status_code == 200
                cuerpo = "".join(response.iter_text())
        app.dependency_overrides.clear()

        assert '"renta_media": 13990.0' in cuerpo
        assert '"opportunity_score": 11.63' in cuerpo