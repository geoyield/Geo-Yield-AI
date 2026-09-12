"""
Tests del router de chat (backend/api/routers/chat.py). Usa mocks sobre
las funciones que orquesta -- sin red real ni llamadas a Gemini.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.api import app
from backend.api.deps import get_session


def _eventos_de(respuesta_texto: str) -> list[dict]:
    import json

    return [json.loads(bloque[6:]) for bloque in respuesta_texto.split("\n\n") if bloque.startswith("data: ")]


class TestChatInformeStream:
    def setup_method(self):
        app.dependency_overrides[get_session] = lambda: object()

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_sin_direccion_ni_distrito_pide_aclaracion(self):
        with patch(
            "backend.api.routers.chat.extraer_intencion",
            return_value={"direccion": None, "distrito_mencionado": None, "pregunta_especifica": None},
        ):
            client = TestClient(app)
            with client.stream("POST", "/api/chat/informe/stream", json={"mensaje": "¿es buena idea abrir un bar?"}) as r:
                eventos = _eventos_de("".join(r.iter_text()))

        assert len(eventos) == 1
        assert eventos[0]["type"] == "aclaracion"
        assert "distrito" in eventos[0]["mensaje"]

    def test_regression_distrito_mencionado_sin_direccion_resuelve_solo_distrito(self):
        # Regresión real: "conozco el distrito de Les Corts, qué me
        # recomiendas" -- no hay dirección exacta, pero sí un distrito
        # utilizable. No usa ningún mock de resolver_distrito_desde_suburb
        # -- se llama la función real, para confirmar que el caso
        # especial de "Les Corts" (donde "Les" es parte del nombre, no
        # un artículo que sobra) sigue funcionando en esta ruta también.
        with patch(
            "backend.api.routers.chat.extraer_intencion",
            return_value={"direccion": None, "distrito_mencionado": "Les Corts", "pregunta_especifica": None},
        ):
            client = TestClient(app)
            with client.stream(
                "POST", "/api/chat/informe/stream",
                json={"mensaje": "Quiero abrir un bar para jóvenes, conozco el distrito de Les Corts, ¿qué me recomiendas?"},
            ) as r:
                eventos = _eventos_de("".join(r.iter_text()))

        assert len(eventos) == 1
        assert eventos[0]["type"] == "aclaracion"
        assert eventos[0]["codi_districte"] == 4  # Les Corts es el distrito 4
        assert "Les Corts" in eventos[0]["mensaje"]

    def test_direccion_no_encontrada_pide_aclaracion(self):
        with (
            patch(
                "backend.api.routers.chat.extraer_intencion",
                return_value={"direccion": "esto no existe", "distrito_mencionado": None, "pregunta_especifica": None},
            ),
            patch("backend.api.routers.chat.geocodificar_direccion", return_value=None),
        ):
            client = TestClient(app)
            with client.stream("POST", "/api/chat/informe/stream", json={"mensaje": "abrir en esto no existe"}) as r:
                eventos = _eventos_de("".join(r.iter_text()))

        assert len(eventos) == 1
        assert eventos[0]["type"] == "aclaracion"
        assert eventos[0]["direccion_buscada"] == "esto no existe"

    def test_regression_zona_no_determinada_devuelve_info_parcial(self):
        # Regresión: cuando la zona no se puede determinar, el mensaje
        # debe especificar QUÉ falta (zona, no distrito) y devolver todo
        # lo que sí se resolvió, para que el frontend pueda prellenar el
        # formulario manual en vez de empezar de cero.
        with (
            patch(
                "backend.api.routers.chat.extraer_intencion",
                return_value={
                    "direccion": "Passeig de Gràcia 50",
                    "distrito_mencionado": None,
                    "pregunta_especifica": None,
                },
            ),
            patch(
                "backend.api.routers.chat.geocodificar_direccion",
                return_value={"lat": 41.39, "lon": 2.16, "direccion_encontrada": "50, Passeig de Gràcia", "codi_districte": 2},
            ),
            patch("backend.api.routers.chat.identificar_zona_pgm", return_value=None),
        ):
            client = TestClient(app)
            with client.stream("POST", "/api/chat/informe/stream", json={"mensaje": "abrir en Passeig de Gràcia 50"}) as r:
                eventos = _eventos_de("".join(r.iter_text()))

        assert len(eventos) == 1
        assert eventos[0]["type"] == "aclaracion"
        assert "zona" in eventos[0]["mensaje"]
        assert eventos[0]["codi_districte"] == 2
        assert eventos[0]["zona_pgm"] is None

    def test_flujo_completo_emite_ubicacion_y_reenvia_eventos_del_informe(self):
        def informe_simulado(session, codi_districte, zona_pgm, pregunta_especifica=None, **kwargs):
            yield {"type": "datos", "datos_distrito": {}, "respuesta_legal": "x", "articulos_citados": []}
            yield {"type": "token", "text": "VERDE"}
            yield {"type": "done", "semaforo": "verde", "resumen": "x"}

        with (
            patch(
                "backend.api.routers.chat.extraer_intencion",
                return_value={
                    "direccion": "Carrer de Sant Pau 1",
                    "distrito_mencionado": None,
                    "pregunta_especifica": "terrazas",
                },
            ),
            patch(
                "backend.api.routers.chat.geocodificar_direccion",
                return_value={"lat": 41.38, "lon": 2.17, "direccion_encontrada": "1, Carrer de Sant Pau", "codi_districte": 1},
            ),
            patch(
                "backend.api.routers.chat.identificar_zona_pgm",
                return_value={"zona_pgm": "nucli_antic", "clau_urb": "12b"},
            ),
            patch("backend.api.routers.chat.generar_informe_viabilidad_stream", side_effect=informe_simulado),
        ):
            client = TestClient(app)
            with client.stream("POST", "/api/chat/informe/stream", json={"mensaje": "abrir en Sant Pau 1, ¿terraza?"}) as r:
                eventos = _eventos_de("".join(r.iter_text()))

        tipos = [e["type"] for e in eventos]
        assert tipos == ["ubicacion", "datos", "token", "done"]
        assert eventos[0]["codi_districte"] == 1
        assert eventos[0]["zona_pgm"] == "nucli_antic"

    def test_mensaje_demasiado_corto_devuelve_422(self):
        client = TestClient(app)
        response = client.post("/api/chat/informe/stream", json={"mensaje": "ab"})
        assert response.status_code == 422