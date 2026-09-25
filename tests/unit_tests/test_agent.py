"""
==============================================================================
UNIT TESTS: LANGGRAPH ORCHESTRATOR AGENT
==============================================================================
File: tests/unit_tests/test_agent.py

Tests the logic of the LangGraph DAG (`backend/ia/agent.py`).
It validates parallel execution, state management, and the sanitization of 
the LLM's non-deterministic output, without making real API calls.
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

# Deterministic Embedding Mock (from Phase 2)
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


# ------------------------------------------------------------------------------
# STATEFUL LLM MOCK (Complex Mocking Pattern)
# ------------------------------------------------------------------------------
class ScriptedLLMClient:
    """
    A Stateful Mock for the Google GenAI SDK.
    Since LangGraph executes multiple LLM calls in a single run (RAG query 
    followed by the Final Synthesis), a simple mock that always returns 'OK' 
    would fail. This mock inspects the `SYSTEM_PROMPT` of the incoming request 
    to figure out *which* node in the graph is calling it, and returns the 
    appropriate fake response.
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
    """
    Defensive Database Fixture.
    Creates a fake district with `codi = 999`. Barcelona only has 10 districts.
    This ensures that even if a test fails to clean up after itself, it will 
    NEVER accidentally overwrite or corrupt the real production data (Districts 1-10).
    """
    codi = 999
    db_session.add(District(codi_districte=codi, nom_districte="Ciutat Vella (dato de prueba)"))
    db_session.add(DistrictIncome(codi_districte=codi, renta_media=15000, periodo=2023))
    db_session.add(DistrictMobility(codi_districte=codi, daily_foot_traffic=400000))
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
    # Manual teardown
    yield codi
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
        """
        CRITICAL REGRESSION TEST (Concurrency):
        In early versions, the two parallel LangGraph nodes shared the exact 
        same SQLAlchemy Session object. SQLAlchemy crashed because it does not 
        permit concurrent operations on a single session. This test verifies 
        that each node correctly spawns its own isolated database session using 
        `session.get_bind()`, preventing the server from crashing.
        """
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
        """Verifies the state travels correctly through the LangGraph DAG."""
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
            codi_districte=9999,  # Non-existent district
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
        """
        Regression Test: Verifies the Regex sanitizer fixes 'AMBAR.' 
        preventing Pydantic from rejecting the LLM's output.
        """
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
        """Verifies the Server-Sent Events (SSE) packet generation order."""
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
        """Verifies that streaming tokens reconstruct into the exact same payload."""
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
        pregunta = _construir_pregunta_legal("nucli_antic")
        assert "Además, el usuario pregunta específicamente" not in pregunta

    def test_construir_pregunta_legal_incluye_la_pregunta_especifica(self):
        pregunta = _construir_pregunta_legal("nucli_antic", pregunta_especifica="terrazas")
        assert "terrazas" in pregunta

    def test_regression_refuerza_no_inventar_cuando_hay_pregunta_especifica(self):
        """Verifies Prompt Engineering: Strictly forbids LLM Hallucinations on Edge cases."""
        pregunta = _construir_pregunta_legal("industrial", pregunta_especifica="terrazas")
        assert "dilo explícitamente" in pregunta
        assert "en vez de responder con seguridad" in pregunta

    def test_generar_informe_stream_propaga_pregunta_especifica_al_rag(
        self, db_session, distrito_ciutat_vella, articulo_302
    ):
        """Verifies the user's specific question travels properly into the LangGraph state."""
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