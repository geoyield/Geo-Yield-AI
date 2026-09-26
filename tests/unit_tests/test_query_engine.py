"""
==============================================================================
UNIT TESTS: RAG QUERY ENGINE & HYBRID RETRIEVAL
==============================================================================
File: tests/unit_tests/test_query_engine.py

Tests the semantic retrieval engine, specifically focusing on the hybrid 
search that merges Zone-specific laws (PGM) with General Municipal laws.
"""

import hashlib

import pytest

from backend.db.models import LegalChunk
from backend.rag.query_engine import build_context, retrieve_relevant_chunks

# ------------------------------------------------------------------------------
# DETERMINISTIC ML MOCKING
# ------------------------------------------------------------------------------
def hash_embed(texts: list[str]) -> list[list[float]]:
    """
    Mock Embedding Function.
    Generates deterministic 384-dimensional vectors based on the SHA256 hash 
    of the text. 
    Why? We cannot use the real Hugging Face model in unit tests because:
    1. It's too slow to load into RAM.
    2. ML model outputs can drift across versions, causing flaky tests.
    This fake function guarantees the exact same mathematical vectors every run.
    """
    result = []
    for t in texts:
        seed = int(hashlib.sha256(t.encode()).hexdigest(), 16)
        result.append([((seed >> (i % 64)) % 1000) / 1000.0 for i in range(384)])
    return result


@pytest.fixture
def articulo_zona(db_session):
    """Fixture: Injects a fake zone-specific law into the test DB."""
    contenido = "Comercial: se permite en zona industrial."
    db_session.add(
        LegalChunk(
            fuente_legal="PGM (Secció V)",
            numero_articulo="311",
            titulo="Zona industrial",
            contenido=contenido,
            versio="original",
            zona_pgm="industrial",
            embedding=hash_embed([contenido])[0],
        )
    )
    db_session.commit()


@pytest.fixture
def articulo_general(db_session):
    """Fixture: Injects a fake general city law (zona_pgm=None) into the test DB."""
    contenido = "El horario máximo de cierre de un bar musical es hasta las 2.30 horas."
    db_session.add(
        LegalChunk(
            fuente_legal="Ordre INT/358/2011",
            numero_articulo="4",
            titulo="Horario general para actividades recreativas musicales",
            contenido=contenido,
            versio="vigente",
            zona_pgm=None,
            embedding=hash_embed([contenido])[0],
        )
    )
    db_session.commit()


class TestRetrieveOrdenaPorRelevanciaGlobal:
    def test_regression_general_chunk_more_relevant_appears_before_zone_chunk(self, db_session):
        """
        Regression Test (Cosine Distance Sorting):
        Before this fix, results were statically concatenated (Zone laws first, 
        General laws second). This test uses hardcoded mathematical vectors to 
        prove that the engine now correctly merges and sorts them by absolute 
        Cosine Similarity, prioritizing the most semantically relevant law 
        regardless of its category.
        """
        # Fake embedding function returning an exact target vector
        def embed_pregunta(textos):
            return [[1.0] + [0.0] * 383 for _ in textos]

        # vector_cercano is mathematically very close to the simulated question
        vector_cercano = [0.99] + [0.0] * 383  
        # vector_lejano is mathematically very far from the question
        vector_lejano = [0.1] + [0.99] * 383   

        db_session.add(LegalChunk(
            fuente_legal="PGM (Secció V)", numero_articulo="1", titulo="t",
            contenido="artículo de zona, lejos de la pregunta",
            versio="original", zona_pgm="industrial", embedding=vector_lejano,
        ))
        db_session.add(LegalChunk(
            fuente_legal="Ordre INT/358/2011", numero_articulo="2", titulo="t",
            contenido="artículo general, muy cerca de la pregunta",
            versio="vigente", zona_pgm=None, embedding=vector_cercano,
        ))
        db_session.commit()

        resultados = retrieve_relevant_chunks(
            db_session, "pregunta", embed_fn=embed_pregunta, top_k=1, zona_pgm="industrial"
        )

        assert len(resultados) == 2
        # The general law (closest vector) MUST be first.
        assert resultados[0].fuente_legal == "Ordre INT/358/2011"
        assert resultados[1].fuente_legal == "PGM (Secció V)"


class TestRetrieveCombinaZonaYGeneral:
    def test_regression_general_law_never_surfaced_when_filtering_by_zone(
        self, db_session, articulo_zona, articulo_general
    ):
        """
        Regression Test:
        Early MVP versions crashed because filtering by 'zona' excluded any law 
        where `zona_pgm` was NULL (general laws). This guarantees the hybrid 
        retrieval fetches both types.
        """
        resultados = retrieve_relevant_chunks(
            db_session, "horario de cierre", embed_fn=hash_embed, top_k=2, zona_pgm="industrial"
        )
        fuentes = {r.fuente_legal for r in resultados}
        assert "PGM (Secció V)" in fuentes
        assert "Ordre INT/358/2011" in fuentes

    def test_without_zona_pgm_no_filter_applied(self, db_session, articulo_zona, articulo_general):
        """Verifies full-corpus search when no zone is specified."""
        resultados = retrieve_relevant_chunks(db_session, "cualquier consulta", embed_fn=hash_embed, top_k=5)
        assert len(resultados) == 2

    def test_only_zone_when_no_general_law_loaded(self, db_session, articulo_zona):
        resultados = retrieve_relevant_chunks(
            db_session, "cualquier consulta", embed_fn=hash_embed, top_k=3, zona_pgm="industrial"
        )
        assert len(resultados) == 1
        assert resultados[0].fuente_legal == "PGM (Secció V)"


class TestBuildContextCitaFuente:
    def test_context_includes_source_law_not_just_article_number(self, db_session, articulo_zona, articulo_general):
        """
        Anti-Hallucination Safeguard:
        "Article 4" by itself is ambiguous if the DB holds 5 different laws.
        This test ensures the final Prompt explicitly specifies the Source Law 
        name to prevent the LLM from mixing contexts.
        """
        resultados = retrieve_relevant_chunks(
            db_session, "horario", embed_fn=hash_embed, top_k=2, zona_pgm="industrial"
        )
        contexto = build_context(resultados)
        assert "Ordre INT/358/2011, Artículo 4" in contexto
        assert "PGM (Secció V), Artículo 311" in contexto