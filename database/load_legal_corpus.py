"""
==============================================================================
RAG PIPELINE: LEGAL CORPUS INGESTION ORCHESTRATOR
==============================================================================
File: database/load_legal_corpus.py

This script acts as the master orchestrator for the RAG data ingestion pipeline.
It iterates through a directory of raw PDFs, chaining the sub-modules:
Extraction -> Chunking & Version Filtering -> Batch Embedding -> DB Upsert.
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
# Explicit import from PostgreSQL dialect to access the ON CONFLICT clause
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.db.connection import resolve_database_url
from backend.db.models import LegalChunk
from backend.rag.chunking import ARTICLE_TO_ZONA_PGM, parse_legal_chunks, select_current_versions
from backend.rag.embeddings import EmbeddingFunction, embed_texts
from backend.rag.pdf_extraction import extract_text_from_pdf

logger = logging.getLogger("geoyield_rag")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

PGM_FUENTE_LEGAL = "PGM (Secció V)"


def load_corpus_from_directory(
    session: Session, pdf_dir: Path, embed_fn: EmbeddingFunction = embed_texts
) -> int:
    """Orchestrates the Extraction, Transformation, and Vectorization processes."""
    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_paths:
        logger.warning(f"No se encontraron PDF en {pdf_dir}")
        return 0

    # 1. Extraction and Chunking
    all_current_chunks = []
    for pdf_path in pdf_paths:
        logger.info(f"Procesando {pdf_path.name}...")
        text = extract_text_from_pdf(pdf_path)
        versions = parse_legal_chunks(text)
        if not versions:
            logger.warning(f"{pdf_path.name}: No articles detected, skipping.")
            continue
        current = select_current_versions(versions)
        for chunk in current:
            all_current_chunks.append((chunk, pdf_path.name))

    if not all_current_chunks:
        logger.warning("No valid articles remained after parsing PDFs.")
        return 0

    # 2. Batch Vectorization (Performance Optimization)
    # We do NOT embed articles one by one inside the previous loop.
    # We collect them all and pass the entire list to the Embedding model. 
    # ML models (like Torch) are highly optimized for batch processing.
    logger.info(f"Generando embeddings para {len(all_current_chunks)} artículos...")
    embeddings = embed_fn([chunk.contenido for chunk, _ in all_current_chunks])

    # 3. Database Preparation & Pre-computation
    records = [
        {
            "fuente_legal": PGM_FUENTE_LEGAL,
            "numero_articulo": chunk.numero_articulo,
            "titulo": chunk.titulo,
            "contenido": chunk.contenido,
            "expedient": chunk.expedient,
            "versio": chunk.versio.value,
            # Pre-compute the relation between Article and Zoning at ingestion time, 
            # saving processing power during user queries (Compute once, read often).
            "zona_pgm": ARTICLE_TO_ZONA_PGM.get(chunk.numero_articulo),
            "documento_origen": source_filename,
            "embedding": embedding,
        }
        for (chunk, source_filename), embedding in zip(all_current_chunks, embeddings)
    ]

    stmt = pg_insert(LegalChunk).values(records)
    update_columns = {
        col: getattr(stmt.excluded, col)
        for col in ("titulo", "contenido", "expedient", "versio", "zona_pgm", "documento_origen", "embedding")
    }

    # ON CONFLICT DO UPDATE allows us to run this script repeatedly without crashing.
    # If a law is updated, it overwrites the old text and old mathematical vector.
    stmt = stmt.on_conflict_do_update(index_elements=["fuente_legal", "numero_articulo"], set_=update_columns)
    session.execute(stmt)

    logger.info(f"legal_chunks: {len(records)} artículos upsert-eados.")
    return len(records)


def run(pdf_dir: Path, engine=None, embed_fn: EmbeddingFunction = embed_texts) -> int:
    load_dotenv()
    if engine is None:
        engine = create_engine(resolve_database_url(), future=True)
    with Session(engine) as session:
        count = load_corpus_from_directory(session, pdf_dir, embed_fn=embed_fn)
        session.commit()
    logger.info("Legal corpus ingestion completed.")
    return count


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m database.load_legal_corpus <path_to_pdf_directory>")
        sys.exit(1)
    run(Path(sys.argv[1]))