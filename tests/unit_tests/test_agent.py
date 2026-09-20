"""
Tests del agente orquestador (backend/ia/agent.py).

Usa hash_embed (determinista, sin red ni modelo real) y un cliente LLM
programable que distingue la llamada del nodo legal de la de síntesis por
el system prompt recibido -- necesario para validar que el informe final
combina de verdad ambos bloques y no solo repite uno de ellos.
"""

import hashlib

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import text

from backend.db.models import Competitor, District, DistrictIncome, DistrictMobility, LegalChunk
from backend.ia.agent import (
    SYNTHESIS_SYSTEM_PROMPT,
    _construir_pregunta_legal,
    generar_informe_viabilidad,
    generar_informe_viabilidad_stream,
    zonas_pgm_disponibles,
)


def hash_embed(texts: list[str]) -> list[list[float]]:
    result = []
    for t in texts:
        seed = int(hashlib.sha256(t.encode()).hexdigest(), 16)
        result.append([((seed >> (i % 64)) % 1000) / 1000.0 for i in range(384)])
    return result


class FakeContent:
    def __init__(self, text):
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeContent(text)]


class ScriptedLLMClient:
    """
    Devuelve una respuesta distinta según el system prompt recibido, para
    poder distinguir la llamada del nodo legal (normativa_legal) de la del
    nodo de síntesis (sintesis_final) -- con un doble que siempre
    devolviera el mismo texto no se podría comprobar que el informe final
    combina de verdad ambos bloques, y no solo repite uno de ellos.
    """

    def __init__(self, synthesis_response: str, legal_response: str = "[respuesta legal de prueba]"):
        self.synthesis_response = synthesis_response
        self.legal_response = legal_response
        self.messages = self

    def create(self, model, max_tokens, system, messages):
        if system == SYNTHESIS_SYSTEM_PROMPT:
            return FakeResponse(self.synthesis_response)
        return FakeResponse(self.legal_response)

    def create_stream(self, model, max_tokens, system, messages):
        # Solo se usa para la síntesis en streaming -- se parte la
        # respuesta programada en palabras, para simular fragmentos
        # reales sin depender de una llamada a Gemini.
        texto = self.synthesis_response if system == SYNTHESIS_SYSTEM_PROMPT else self.legal_response
        palabras = texto.split(" ")
        for i, palabra in enumerate(palabras):
            yield palabra + (" " if i < len(palabras) - 1 else "")


@pytest.fixture
def distrito_ciutat_vella(db_session):
    # codi_districte=999 a propósito: Barcelona solo tiene distritos 1-10
    # (BARCELONA_DISTRICTS en backend/etl/competitors.py), así que este
    # valor nunca puede coincidir con datos reales ya cargados en un
    # entorno de desarrollo con la Fase 1 completada -- evita el riesgo de
    # borrar o pisar datos reales del usuario al limpiar tras el test.
    codi = 999
    db_session.add(District(codi_districte=codi, nom_districte="Ciutat Vella (dato de prueba)"))
    db_session.add(DistrictIncome(codi_districte=codi, renta_media=15000, periodo=2023))
    db_session.add(DistrictMobility(codi_districte=codi, daily_foot_traffic=400000))
    # flush() explícito antes de añadir Competitor: sin él, en pruebas
    # reales SQLAlchemy no garantizaba que el INSERT de districts se
    # ejecutara antes que el de competitors, que lo referencia por FK --
    # un solo commit() con todo junto podía fallar con
    # "Key (codi_districte)=(999) is not present in table districts".
    db_session.flush()
    db_session.add(
        Competitor(
            id_global="test-1",
            nom_activitat="Bars",
            nom_grup_activitat="Restaurants, bars i hotels",
            codi_districte=codi,
            geom=WKTElement("POINT(2.17 41.38)", srid=4326),
        )
    )
    db_session.commit()
    yield codi
    # conftest.py solo trunca legal_chunks entre tests, no estas tablas de
    # la Fase 1 -- se limpian aquí para no contaminar otros tests.
    db_session.execute(text("DELETE FROM competitors WHERE codi_districte = :codi"), {"codi": codi})
    db_session.execute(text("DELETE FROM district_income WHERE codi_districte = :codi"), {"codi": codi})
    db_session.execute(text("DELETE FROM district_mobility WHERE codi_districte = :codi"), {"codi": codi})
    db_session.execute(text("DELETE FROM districts WHERE codi_districte = :codi"), {"codi": codi})
    db_session.commit()


@pytest.fixture
def articulo_302(db_session):
    contenido = "Comercial: se permite en edificios exclusivos."
    db_session.add(
        LegalChunk(
            fuente_legal="PGM (Secció V)",  # obligatorio desde la migración 0005
            numero_articulo="302",
            titulo="Zona de nucli antic",
            contenido=contenido,
            expedient="test/000000",
            versio="consolidat",
            zona_pgm="nucli_antic",
            documento_origen="test.pdf",
            embedding=hash_embed([contenido])[0],
        )
    )
    db_session.commit()


class TestZonasPgmDisponibles:
    def test_returns_only_zones_with_data(self, db_session, articulo_302):
        assert zonas_pgm_disponibles(db_session) == ["nucli_antic"]

    def test_empty_when_no_legal_chunks(self, db_session):
        assert zonas_pgm_disponibles(db_session) == []


class TestGenerarInformeViabilidad:
    def test_regression_parallel_nodes_do_not_crash(self, db_session, distrito_ciutat_vella, articulo_302):
        # Regresión de un bug real: datos_socioeconomicos y normativa_legal
        # se ejecutan en PARALELO (ambos arrancan desde START en el grafo).
        # Compartir una única Session de SQLAlchemy entre nodos que corren
        # a la vez revienta con "This session is provisioning a new
        # connection; concurrent operations are not permitted". Cada nodo
        # paralelo debe usar su propia sesión, derivada del mismo motor.
        client = ScriptedLLMClient(synthesis_response="VERDE\nresumen de prueba")
        informe = generar_informe_viabilidad(
            db_session,
            codi_districte=distrito_ciutat_vella,
            zona_pgm="nucli_antic",
            embed_fn=hash_embed,
            llm_client=client,
        )
        assert informe["semaforo"] == "verde"

    def test_combines_both_blocks_correctly(self, db_session, distrito_ciutat_vella, articulo_302):
        client = ScriptedLLMClient(
            synthesis_response="AMBAR\nresumen de sintesis",
            legal_response="[texto legal distintivo]",
        )
        informe = generar_informe_viabilidad(
            db_session,
            codi_districte=distrito_ciutat_vella,
            zona_pgm="nucli_antic",
            embed_fn=hash_embed,
            llm_client=client,
        )
        assert informe["semaforo"] == "ambar"
        assert informe["resumen"] == "resumen de sintesis"
        assert informe["respuesta_legal"] == "[texto legal distintivo]"
        assert informe["articulos_citados"] == [{"numero_articulo": "302", "fuente_legal": "PGM (Secció V)"}]
        assert informe["datos_distrito"]["nom_districte"] == "Ciutat Vella (dato de prueba)"

    def test_missing_district_data_does_not_crash(self, db_session, articulo_302):
        client = ScriptedLLMClient(synthesis_response="ROJO\nsin datos de distrito")
        informe = generar_informe_viabilidad(
            db_session,
            codi_districte=9999,  # distrito que no existe, distinto del 999 de la otra fixture
            zona_pgm="nucli_antic",
            embed_fn=hash_embed,
            llm_client=client,
        )
        assert informe["datos_distrito"] == {}
        assert informe["semaforo"] == "rojo"

    def test_falls_back_gracefully_on_unrecognized_semaforo(self, db_session, distrito_ciutat_vella, articulo_302):
        client = ScriptedLLMClient(synthesis_response="Esto no empieza con un semáforo válido.")
        informe = generar_informe_viabilidad(
            db_session,
            codi_districte=distrito_ciutat_vella,
            zona_pgm="nucli_antic",
            embed_fn=hash_embed,
            llm_client=client,
        )
        assert informe["semaforo"] == "ambar"  # fallback neutro, no revienta

    def test_regression_trailing_period_after_semaforo_still_recognized(
        self, db_session, distrito_ciutat_vella, articulo_302
    ):
        # Regresión real: el LLM devolvió "AMBAR." (con punto final) en
        # producción, y como la comparación era exacta, caía en el
        # fallback -- además de perder el semáforo real, el resumen
        # quedaba con "AMBAR." pegado al principio, filtrando la palabra
        # del semáforo hacia el texto visible.
        client = ScriptedLLMClient(synthesis_response="AMBAR.\nResumen de prueba tras el punto final.")
        informe = generar_informe_viabilidad(
            db_session,
            codi_districte=distrito_ciutat_vella,
            zona_pgm="nucli_antic",
            embed_fn=hash_embed,
            llm_client=client,
        )
        assert informe["semaforo"] == "ambar"
        assert informe["resumen"] == "Resumen de prueba tras el punto final."
        assert "AMBAR" not in informe["resumen"]  # no debe haberse filtrado al resumen


class TestGenerarInformeViabilidadStream:
    def test_yields_datos_then_tokens_then_done_in_order(self, db_session, distrito_ciutat_vella, articulo_302):
        client = ScriptedLLMClient(synthesis_response="VERDE\nResumen de prueba en streaming.")
        eventos = list(
            generar_informe_viabilidad_stream(
                db_session, codi_districte=distrito_ciutat_vella, zona_pgm="nucli_antic",
                embed_fn=hash_embed, llm_client=client,
            )
        )
        tipos = [e["type"] for e in eventos]
        assert tipos[0] == "datos"
        assert tipos[-1] == "done"
        assert all(t == "token" for t in tipos[1:-1])
        assert len(tipos) > 2  # al menos un token real entre "datos" y "done"

    def test_regression_concatenated_tokens_match_non_streaming_result(
        self, db_session, distrito_ciutat_vella, articulo_302
    ):
        # Regresión: la concatenación de los fragmentos en streaming debe
        # dar exactamente el mismo semáforo y resumen que la versión sin
        # streaming para la misma respuesta -- ambas comparten
        # _parsear_semaforo_y_resumen, pero conviene comprobarlo de punta
        # a punta por si el trocear en palabras introdujera alguna
        # diferencia (p. ej. espacios perdidos entre fragmentos).
        client = ScriptedLLMClient(synthesis_response="AMBAR\nResumen con varias palabras para probar la unión.")
        eventos = list(
            generar_informe_viabilidad_stream(
                db_session, codi_districte=distrito_ciutat_vella, zona_pgm="nucli_antic",
                embed_fn=hash_embed, llm_client=client,
            )
        )
        evento_done = eventos[-1]
        assert evento_done["semaforo"] == "ambar"
        assert evento_done["resumen"] == "Resumen con varias palabras para probar la unión."

    def test_datos_event_includes_district_data_and_citations(self, db_session, distrito_ciutat_vella, articulo_302):
        client = ScriptedLLMClient(synthesis_response="VERDE\nResumen.", legal_response="[texto legal distintivo]")
        eventos = list(
            generar_informe_viabilidad_stream(
                db_session, codi_districte=distrito_ciutat_vella, zona_pgm="nucli_antic",
                embed_fn=hash_embed, llm_client=client,
            )
        )
        evento_datos = eventos[0]
        assert evento_datos["type"] == "datos"
        assert evento_datos["datos_distrito"]["nom_districte"] == "Ciutat Vella (dato de prueba)"
        assert evento_datos["respuesta_legal"] == "[texto legal distintivo]"
        assert evento_datos["articulos_citados"] == [{"numero_articulo": "302", "fuente_legal": "PGM (Secció V)"}]


class TestPreguntaEspecificaDelChat:
    def test_construir_pregunta_legal_sin_pregunta_especifica_no_cambia(self):
        # El comportamiento existente (sin pregunta específica) no debe
        # cambiar en absoluto -- mismo texto que antes de esta extensión.
        pregunta = _construir_pregunta_legal("nucli_antic")
        assert "Además, el usuario pregunta específicamente" not in pregunta

    def test_construir_pregunta_legal_incluye_la_pregunta_especifica(self):
        pregunta = _construir_pregunta_legal("nucli_antic", pregunta_especifica="terrazas")
        assert "terrazas" in pregunta

    def test_regression_refuerza_no_inventar_cuando_hay_pregunta_especifica(self):
        # Regresión directa del riesgo de invención confirmado en esta
        # sesión (el caso de las terrazas): cuando hay una pregunta
        # específica, la pregunta legal debe reforzar explícitamente que
        # si no hay normativa concreta sobre ello, hay que decirlo, no
        # inventarlo.
        pregunta = _construir_pregunta_legal("industrial", pregunta_especifica="terrazas")
        assert "dilo explícitamente" in pregunta
        assert "en vez de responder con seguridad" in pregunta

    def test_generar_informe_stream_propaga_pregunta_especifica_al_rag(
        self, db_session, distrito_ciutat_vella, articulo_302
    ):
        # Confirma que la pregunta específica llega de verdad hasta la
        # llamada al RAG, no solo que la función auxiliar la construye
        # bien de forma aislada.
        preguntas_recibidas = []

        class ClienteQueRegistraPreguntas(ScriptedLLMClient):
            def create(self, model, max_tokens, system, messages):
                if system != SYNTHESIS_SYSTEM_PROMPT:
                    preguntas_recibidas.append(messages[0]["content"])
                return super().create(model, max_tokens, system, messages)

        client = ClienteQueRegistraPreguntas(synthesis_response="VERDE\nResumen.")
        list(
            generar_informe_viabilidad_stream(
                db_session, codi_districte=distrito_ciutat_vella, zona_pgm="nucli_antic",
                embed_fn=hash_embed, llm_client=client, pregunta_especifica="horarios de cierre",
            )
        )
        assert len(preguntas_recibidas) == 1
        assert "horarios de cierre" in preguntas_recibidas[0]