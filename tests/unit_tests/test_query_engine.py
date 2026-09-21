"""
Tests de retrieve_relevant_chunks combinando normativa de zona (PGM) con
normativa general (leyes/órdenes que aplican en toda la ciudad, migración
0005).
"""

import hashlib

import pytest

from backend.db.models import LegalChunk
from backend.rag.query_engine import build_context, retrieve_relevant_chunks


def hash_embed(texts: list[str]) -> list[list[float]]:
    result = []
    for t in texts:
        seed = int(hashlib.sha256(t.encode()).hexdigest(), 16)
        result.append([((seed >> (i % 64)) % 1000) / 1000.0 for i in range(384)])
    return result


@pytest.fixture
def articulo_zona(db_session):
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
        # Regresión: antes, los resultados se concatenaban en un orden
        # fijo (zona primero, generales después), sin importar cuál era
        # realmente más relevante. Con embeddings fijados a mano (no el
        # hash_embed habitual, que no permite controlar distancias
        # exactas), se sabe de antemano qué artículo debe quedar primero.
        def embed_pregunta(textos):
            return [[1.0] + [0.0] * 383 for _ in textos]

        vector_cercano = [0.99] + [0.0] * 383  # muy cerca del vector de la pregunta
        vector_lejano = [0.1] + [0.99] * 383  # lejos del vector de la pregunta

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
        # El general (más cercano) debe ir primero, aunque la concatenación
        # original (zona primero) lo habría puesto en segundo lugar.
        assert resultados[0].fuente_legal == "Ordre INT/358/2011"
        assert resultados[1].fuente_legal == "PGM (Secció V)"


class TestRetrieveCombinaZonaYGeneral:
    def test_regression_general_law_never_surfaced_when_filtering_by_zone(
        self, db_session, articulo_zona, articulo_general
    ):
        # Regresión: antes de la migración 0005, filtrar por zona_pgm
        # excluía CUALQUIER artículo con zona_pgm NULL -- la normativa
        # general (horarios, alcohol...) nunca podía aparecer en una
        # consulta filtrada por zona, aunque fuera justo lo relevante.
        resultados = retrieve_relevant_chunks(
            db_session, "horario de cierre", embed_fn=hash_embed, top_k=2, zona_pgm="industrial"
        )
        fuentes = {r.fuente_legal for r in resultados}
        assert "PGM (Secció V)" in fuentes
        assert "Ordre INT/358/2011" in fuentes

    def test_without_zona_pgm_no_filter_applied(self, db_session, articulo_zona, articulo_general):
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
        # Regresión: con varias normas, "Artículo 4" por sí solo es
        # ambiguo -- el contexto debe dejar claro de qué norma es cada uno.
        resultados = retrieve_relevant_chunks(
            db_session, "horario", embed_fn=hash_embed, top_k=2, zona_pgm="industrial"
        )
        contexto = build_context(resultados)
        assert "Ordre INT/358/2011, Artículo 4" in contexto
        assert "PGM (Secció V), Artículo 311" in contexto