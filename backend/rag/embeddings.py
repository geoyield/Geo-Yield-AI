"""
==============================================================================
RAG PIPELINE: LOCAL EMBEDDINGS MODEL
==============================================================================
File: backend/rag/embeddings.py

This module handles the mathematical vectorization of legal texts.
It uses a lightweight, open-source local model (Sentence-Transformers) 
to embed text into 384-dimensional vectors at zero cost, bypassing the 
need for paid external APIs (like OpenAI).

Performance Feature:
The Heavy Machine Learning model (Torch) is loaded lazily and cached in 
memory. It only consumes RAM upon the first actual usage, preventing slow 
boot times when other modules import the EMBEDDING_DIM constant.
"""

from typing import Protocol

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Singleton cache for the model instance
_model = None


class EmbeddingFunction(Protocol):
    """
    Dependency Injection Interface (Protocol).
    Any function used to embed text (e.g., in `database/load_legal_corpus.py` 
    or inside Unit Tests) must match this signature. This allows us to inject 
    a fake/mock embedding function during testing without coupling the tests 
    to the heavy Hugging Face model.
    """

    def __call__(self, texts: list[str]) -> list[list[float]]: ...


def _get_model():
    global _model
    """
    Lazy Loader (Singleton Pattern).
    Loads the Hugging Face model into memory only the first time it is called.
    """
    if _model is None:
        # Lazy Import: 'sentence_transformers' drags the massive PyTorch library 
        # into memory. We do not want to pay this heavy import tax globally, 
        # especially during Pytest runs that use Mock embedding functions.
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    The concrete implementation of EmbeddingFunction using the local model.

    Mathematical Design Note:
    `normalize_embeddings=True` forces the vectors to have a unit norm (L2).
    Why? Because mathematically, when vectors are normalized, Cosine Distance 
    becomes proportional to Inner Product. This allows PostgreSQL (pgvector) 
    to use the `<=>` operator over the HNSW index, drastically speeding up 
    the semantic similarity search.
    """
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()
