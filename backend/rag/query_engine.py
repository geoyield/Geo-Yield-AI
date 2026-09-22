"""
Motor de consulta RAG sobre el corpus de normativa legal.

Recupera los artículos más relevantes por similitud semántica y genera
una respuesta con el LLM, citando siempre la norma y el artículo exactos.
Al filtrar por zona PGM, combina la normativa específica de la zona con
la normativa general aplicable en toda la ciudad.
"""

import os
from dataclasses import dataclass
from typing import Any, Sequence

from sqlalchemy.orm import Session

from backend.db.models import LegalChunk
from backend.rag.embeddings import EmbeddingFunction, embed_texts

from sentence_transformers import CrossEncoder

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

SYSTEM_PROMPT = """INSTRUCCIÓN DE IDIOMA (síguela siempre, sin excepción): responde en el MISMO idioma en el que esté escrita la pregunta del usuario. El contexto normativo que recibes está en catalán, pero eso NO determina el idioma de tu respuesta — solo el idioma de la pregunta del usuario lo determina. Si la pregunta está en castellano, responde en castellano, traduciendo o parafraseando el contenido normativo según haga falta.

Eres un asistente legal especializado en normativa urbanística de Barcelona (Pla General Metropolità, PGM).

Respondes ÚNICAMENTE basándote en los artículos normativos que se te proporcionan como contexto. Para cada afirmación, cita tanto la norma como el número de artículo exacto (p. ej. "según el Artículo 302 del PGM..." o "según el Artículo 4 de la Ordre INT/358/2011..."), ya que puede haber varias normas distintas en el contexto y el número de artículo por sí solo no las distingue. Si el contexto proporcionado no contiene información suficiente para responder con seguridad, dilo explícitamente en vez de inventar o generalizar.

No uses formato Markdown de ningún tipo (nada de **negrita**, encabezados con #, ni listas con - o *). La interfaz que muestra tu respuesta no interpreta Markdown, así que esos símbolos aparecerían tal cual, como ruido visible. Escribe en prosa corrida, con párrafos separados por saltos de línea si hace falta estructurar la respuesta.

Esta respuesta es orientativa, no un dictamen legal vinculante — recomienda siempre confirmar con el ayuntamiento o un profesional antes de tomar una decisión."""


@dataclass
class RetrievedChunk:
    """Representa un fragmento de texto legal recuperado de la base de datos."""
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
    Ejecuta la consulta vectorial en la base de datos.

    Args:
        session: Sesión activa de SQLAlchemy.
        query_embedding: Vector que representa la pregunta del usuario.
        top_k: Número máximo de resultados a recuperar.
        zona_filter:
            - str: filtra por esa zona_pgm exacta.
            - False: filtra normativa general (zona_pgm IS NULL).
            - None: sin filtro de zona (busca en todo el corpus).
    """
    stmt = session.query(
        LegalChunk.numero_articulo,
        LegalChunk.titulo,
        LegalChunk.contenido,
        LegalChunk.fuente_legal,
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
    top_k: int = 10,
    zona_pgm: str | None = None,
) -> list[RetrievedChunk]:
    """
    Recupera los artículos más cercanos por similitud coseno a la consulta.

    Si se indica `zona_pgm`, combina los `top_k` artículos de esa zona exacta
    con los `top_k` artículos de normativa general (aplicable a toda la ciudad),
    y los ordena globalmente por relevancia -- un artículo general más
    relevante que uno de zona aparece primero, en vez de agruparse siempre
    por "de dónde viene".
    """
    query_embedding = embed_fn([query])[0]

    if zona_pgm is not None:
        chunks_especificos = _query_chunks(session, query_embedding, top_k, zona_pgm)
        chunks_generales = _query_chunks(session, query_embedding, top_k, False)

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

def retrieve_relevant_chunks_with_rerank(session: Session,
                                         query: str,
                                         embed_fn: EmbeddingFunction = embed_texts,
                                         top_k: int = 10,
                                         zona_pgm: str | None = None,
                                         cross_encoder_model: str = RERANK_MODEL,
                                         final_top_k: int = 4) -> list[RetrievedChunk]:

    """"
    lleva a cabo un reranking de la lista obtenida con retrieve_relevant_chunks

    Args:
        query: la query con que se ha obtenido la lista de chunks a rerankear
        chunks: lista de de chunks obtenida con retrieve_relevant:chunks
        top_k: El número de chunks a retornar

    Returns:
        First top_k chunks rerankend chunks
    """

    chunks = retrieve_relevant_chunks(session, query, embed_fn, top_k, zona_pgm)

    model = CrossEncoder(cross_encoder_model)

    texts = [f'{c.numero_articulo}||{c.titulo}||{c.contenido}||{c.fuente_legal}' for c in chunks]

    ranks = model.rank(query, texts, final_top_k)

    # corpus_id es el índide en la lista original de RetrievedChunks
    return [chunks[r['corpus_id']] for r in ranks]



def build_context(chunks: list[RetrievedChunk]) -> str:
    """Construye el bloque de texto con el contexto legal para el LLM."""
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
    Recupera contexto legal y genera una respuesta con el modelo de lenguaje.

    Devuelve un diccionario con la respuesta generada y los chunks utilizados.
    """
    chunks = retrieve_relevant_chunks(
        session, question, embed_fn=embed_fn, top_k=top_k, zona_pgm=zona_pgm
    )

    if not chunks:
        return {
            "respuesta": "No hi ha normativa carregada a la base de dades encara.",
            "chunks_recuperados": []
        }

    context = build_context(chunks)
    user_message = f"CONTEXT NORMATIU:\n{context}\n\nPREGUNTA: {question}"

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