"""
==============================================================================
ETL PIPELINE: GENERAL LAW INGESTION (BOE, DOGC)
==============================================================================
File: database/load_general_law.py

Orchestrates the ingestion of National and Regional laws that apply to the 
entire city, regardless of the specific urban zone.

Architectural Difference:
Unlike the local PGM laws (where 1 PDF = 1 Article), here 1 PDF = 1 Full Law 
(containing dozens of articles). Because PDF filenames are unreliable, the 
Legal Source Name (`fuente_legal`) is explicitly required as a CLI argument.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.db.connection import resolve_database_url
from backend.db.models import LegalChunk
from backend.rag.general_chunking import parse_articulo_general
from backend.rag.embeddings import EmbeddingFunction, embed_texts
from backend.rag.pdf_extraction import extract_text_from_pdf

from backend.observability import configure_logging, get_logger

logger = get_logger("etl.general_law")


def load_general_law(
    session: Session, pdf_path: Path, fuente_legal: str, embed_fn: EmbeddingFunction = embed_texts
) -> int:
    """Orchestrates Extraction, NLP Chunking, Vectorization, and Upserting."""
    logger.info(f"Procesando {pdf_path.name} como '{fuente_legal}'...")
    text = extract_text_from_pdf(pdf_path)
    articulos = parse_articulo_general(text)

    if not articulos:
        logger.warning(f"{pdf_path.name}: no se detectó ningún artículo. Revisa el formato antes de reintentar.")
        return 0

    logger.info(f"Generando embeddings para {len(articulos)} artículos de '{fuente_legal}'...")
    # ------------------------------------------------------------------------------
    # NLP OPTIMIZATION: SEMANTIC CONCATENATION
    # ------------------------------------------------------------------------------
    # We embed `Title + Content` together. 
    # Why? In poorly formatted government documents (e.g., Decret 32/2005), 
    # there is no real title; the law starts immediately after the article number.
    # The NLP parser mistakenly grabs the first sentence (which contains the most 
    # crucial keywords) and labels it "Title". If we only vectorized the "Content", 
    # the semantic search (Cosine Distance) would completely miss those keywords.
    embeddings = embed_fn([f"{a.titulo}. {a.contenido}" for a in articulos])

    records = [
        {
            "fuente_legal": fuente_legal,
            "numero_articulo": a.numero_articulo,
            "titulo": a.titulo,
            "contenido": a.contenido,
            "expedient": None,
            "versio": "vigente",
            # Intentional NULL: This law applies globally, not to a specific zone.
            "zona_pgm": None,  
            "documento_origen": pdf_path.name,
            "embedding": embedding,
        }
        for a, embedding in zip(articulos, embeddings)
    ]

    # Idempotent Upsert Strategy (Zero Downtime)
    stmt = pg_insert(LegalChunk).values(records)
    update_columns = {
        col: getattr(stmt.excluded, col)
        for col in ("titulo", "contenido", "expedient", "versio", "zona_pgm", "documento_origen", "embedding")
    }
    stmt = stmt.on_conflict_do_update(index_elements=["fuente_legal", "numero_articulo"], set_=update_columns)
    session.execute(stmt)

    logger.info(f"legal_chunks: {len(records)} artículos de '{fuente_legal}' upsert-eados.")
    return len(records)


def run(pdf_path: Path, fuente_legal: str, engine=None, embed_fn: EmbeddingFunction = embed_texts) -> int:
    load_dotenv()
    if engine is None:
        engine = create_engine(resolve_database_url(), future=True)
    with Session(engine) as session:
        count = load_general_law(session, pdf_path, fuente_legal, embed_fn=embed_fn)
        session.commit()
    logger.info("General law ingestion completed.")
    return count


if __name__ == "__main__":
    configure_logging()
    if len(sys.argv) != 3:
        print('Uso: python -m database.load_general_law <ruta.pdf> "<Law Name>"')
        sys.exit(1)
    run(Path(sys.argv[1]), sys.argv[2])