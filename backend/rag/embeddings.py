"""
Embeddings locales para el motor RAG legal (sentence-transformers, coste
cero, decisión ya validada con el usuario).

El modelo se carga de forma perezosa (solo al primer uso real) y cacheada
en memoria — evita el coste de cargarlo si el módulo se importa pero no se
usa (p. ej. en tests que inyectan su propia función de embedding).
"""

from typing import Protocol

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

_model = None


class EmbeddingFunction(Protocol):
    """
    Contrato que debe cumplir cualquier función de embedding usada por el
    pipeline de ingesta (ver database/load_legal_corpus.py). Se define como
    Protocol para poder inyectar una función falsa en los tests sin
    necesidad de heredar de una clase base — cualquier callable con esta
    firma vale.
    """

    def __call__(self, texts: list[str]) -> list[list[float]]: ...


def _get_model():
    global _model
    if _model is None:
        # Import perezoso: sentence-transformers es una dependencia pesada
        # (arrastra torch), no queremos pagar ese coste de import solo por
        # importar este módulo si al final se usa una función inyectada.
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Implementación real de EmbeddingFunction, usando el modelo local.

    normalize_embeddings=True: normaliza a norma unitaria, para que la
    distancia coseno (el operador <=> que usa el índice HNSW de la
    migración 0003) sea directamente comparable entre vectores.
    """
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()
