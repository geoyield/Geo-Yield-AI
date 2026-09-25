"""
==============================================================================
RAG PIPELINE: SEMANTIC QUERY ENGINE
==============================================================================
File: backend/rag/query_engine.py

This module orchestrates the core Retrieval-Augmented Generation (RAG) flow.
It vectorizes the user's question, performs a semantic similarity search 
against the PostGIS (pgvector) database, builds a context prompt, and 
generates the final answer using the LLM (Gemini via Adapter).
"""

import os
from dataclasses import dataclass
from typing import Any, Sequence

from sqlalchemy.orm import Session

from backend.db.models import LegalChunk
from backend.rag.embeddings import EmbeddingFunction, embed_texts

# Allows seamless upgrades to newer Gemini models via environment variables
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ------------------------------------------------------------------------------
# PROMPT ENGINEERING
# ------------------------------------------------------------------------------
# 1. Cross-lingual mapping: The corpus is in Catalan, but the LLM is instructed 
#    to dynamically translate the answer to the user's query language.
# 2. Strict Citation: Anti-hallucination mechanism. The LLM must cite the source.
# 3. UI Constraint: Markdown is banned because the frontend map popups do not 
#    support rendering Markdown tokens (*, #), preventing ugly raw text on the UI.
SYSTEM_PROMPT = """INSTRUCCIÓN DE IDIOMA (síguela siempre, sin excepción): responde en el MISMO idioma en el que esté escrita la pregunta del usuario. El contexto normativo que recibes está en catalán, pero eso NO determina el idioma de tu respuesta — solo el idioma de la pregunta del usuario lo determina. Si la pregunta está en castellano, responde en castellano, traduciendo o parafraseando el contenido normativo según haga falta.

Eres un asistente legal especializado en normativa urbanística de Barcelona (Pla General Metropolità, PGM).

Respondes ÚNICAMENTE basándote en los artículos normativos que se te proporcionan como contexto. Para cada afirmación, cita tanto la norma como el número de artículo exacto (p. ej. "según el Artículo 302 del PGM..." o "según el Artículo 4 de la Ordre INT/358/2011..."), ya que puede haber varias normas distintas en el contexto y el número de artículo por sí solo no las distingue. Si el contexto proporcionado no contiene información suficiente para responder con seguridad, dilo explícitamente en vez de inventar o generalizar.

No uses formato Markdown de ningún tipo (nada de **negrita**, encabezados con #, ni listas con - o *). La interfaz que muestra tu respuesta no interpreta Markdown, así que esos símbolos aparecerían tal cual, como ruido visible. Escribe en prosa corrida, con párrafos separados por saltos de línea si hace falta estructurar la respuesta.

Esta respuesta es orientativa, no un dictamen legal vinculante — recomienda siempre confirmar con el ayuntamiento o un profesional antes de tomar una decisión."""


@dataclass
class RetrievedChunk:
    """DTO for chunks successfully retrieved from the Vector Database."""
    numero_articulo: str
    titulo: str
    contenido: str
    distancia: float
    fuente_legal: str = "PGM"


def _query_chunks(
    session: Session,
    query_embedding: list[float],
    top_k: int,
    zona_filter: str | bool | None
) -> Sequence[Any]:
    """
    Executes the vector similarity search in PostGIS.

    Args:
        session: SQLAlchemy active session.
        query_embedding: The vectorized user question.
        top_k: Limit of chunks to retrieve.
        zona_filter: 
            - str: Exact zoning code (e.g., 'nucli_antic').
            - False: General City Law (zona_pgm IS NULL).
            - None: Unfiltered search across the entire corpus.
    """
    stmt = session.query(
        LegalChunk.numero_articulo,
        LegalChunk.titulo,
        LegalChunk.contenido,
        LegalChunk.fuente_legal,
        # pgvector's <=> operator translates to cosine_distance in SQLAlchemy
        LegalChunk.embedding.cosine_distance(query_embedding).label("distancia"),
    )

    if zona_filter is False:
        stmt = stmt.filter(LegalChunk.zona_pgm.is_(None))
    elif zona_filter is not None:
        stmt = stmt.filter(LegalChunk.zona_pgm == zona_filter)

    return stmt.order_by("distancia").limit(top_k).all()


def retrieve_relevant_chunks(
    session: Session,
    query: str,
    embed_fn: EmbeddingFunction = embed_texts,
    top_k: int = 3,
    zona_pgm: str | None = None,
) -> list[RetrievedChunk]:
    """
    Domain-Aware Retrieval Strategy.
    
    A naïve RAG simply queries the entire DB. Here, if the user asks about a 
    specific zone (e.g., 'nucli_antic'), we query the top K laws for that exact 
    zone, AND the top K general city laws. We then merge both lists and sort 
    them globally by absolute cosine distance. This ensures the LLM receives a 
    balanced context of both hyper-local zoning rules and general municipal codes.
    """
    # 1. Embed the user's natural language question
    query_embedding = embed_fn([query])[0]

    # 2. Execute Hybrid Retrieval
    if zona_pgm is not None:
        chunks_especificos = _query_chunks(session, query_embedding, top_k, zona_pgm)
        chunks_generales = _query_chunks(session, query_embedding, top_k, False)

        # Merge and sort by the closest semantic match across both sub-queries
        results = list(chunks_especificos) + list(chunks_generales)
        results.sort(key=lambda r: r.distancia)
    else:
        results = list(_query_chunks(session, query_embedding, top_k, None))

    return [
        RetrievedChunk(
            numero_articulo=r.numero_articulo,
            titulo=r.titulo,
            contenido=r.contenido,
            distancia=r.distancia,
            fuente_legal=r.fuente_legal
        )
        for r in results
    ]


def build_context(chunks: list[RetrievedChunk]) -> str:
    """Compiles the retrieved DTOs into a single prompt block for the LLM."""
    return "\n\n".join(
        f"--- {c.fuente_legal}, Artículo {c.numero_articulo}: {c.titulo} ---\n{c.contenido}"
        for c in chunks
    )


def generate_answer(
    session: Session,
    question: str,
    embed_fn: EmbeddingFunction = embed_texts,
    llm_client: Any = None,
    model: str = DEFAULT_MODEL,
    top_k: int = 3,
    max_tokens: int = 4096,
    zona_pgm: str | None = None,
) -> dict[str, Any]:
    """
    Final Generation Step (The 'G' in RAG).
    Passes the strict system instructions, the retrieved legal context, and 
    the user's question to the LLM Adapter.
    """
    chunks = retrieve_relevant_chunks(
        session, question, embed_fn=embed_fn, top_k=top_k, zona_pgm=zona_pgm
    )

    # Fast-fail if the database is empty or no relevant vectors are found
    if not chunks:
        # Known Bug (Technical Debt): This fallback is hardcoded in Catalan, 
        # violating the dynamic language rule defined in the SYSTEM_PROMPT.
        return {
            "respuesta": "No hi ha normativa carregada a la base de dades encara.",
            "chunks_recuperados": []
        }

    context = build_context(chunks)
    user_message = f"CONTEXT NORMATIU:\n{context}\n\nPREGUNTA: {question}"

    # Lazy load the Adapter to prevent cyclic dependencies or unnecessary imports
    if llm_client is None:
        from backend.rag.gemini_adapter import GeminiAsAnthropicAdapter
        llm_client = GeminiAsAnthropicAdapter()

    response = llm_client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return {
        "respuesta": response.content[0].text,
        "chunks_recuperados": chunks
    }