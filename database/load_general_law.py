"""
Orquestador de carga de normas generales (BOE, DOGC): leyes, órdenes y
decretos que aplican en toda la ciudad, no solo en una zona PGM concreta.

Distinto de load_legal_corpus.py en un punto clave: allí un PDF = un
artículo del PGM (formato NUMAMB); aquí UN PDF = UNA NORMA COMPLETA, que
puede contener varios artículos (formato "Artículo N" de BOE/DOGC, ver
backend/rag/chunking_general.py). Por eso el nombre de la norma
(`fuente_legal`) se recibe como argumento explícito -- no se puede
derivar con fiabilidad del nombre del fichero.

Los artículos cargados aquí quedan con zona_pgm=NULL a propósito: son
normativa general, no específica de ninguna zona urbanística. El motor de
consulta (backend/rag/query_engine.py) los combina automáticamente con la
normativa de zona cuando corresponde.

Uso:
    python -m database.load_general_law data/raw/legal/horarios.pdf "Ordre INT/358/2011"
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.db.connection import resolve_database_url
from backend.db.models import LegalChunk
from backend.rag.chunking_general import parse_articulo_general
from backend.rag.embeddings import EmbeddingFunction, embed_texts
from backend.rag.pdf_extraction import extract_text_from_pdf

from backend.observability import configure_logging, get_logger

logger = get_logger("etl.general_law")


def load_general_law(
    session: Session, pdf_path: Path, fuente_legal: str, embed_fn: EmbeddingFunction = embed_texts
) -> int:
    logger.info(f"Procesando {pdf_path.name} como '{fuente_legal}'...")
    text = extract_text_from_pdf(pdf_path)
    articulos = parse_articulo_general(text)

    if not articulos:
        logger.warning(f"{pdf_path.name}: no se detectó ningún artículo. Revisa el formato antes de reintentar.")
        return 0

    logger.info(f"Generando embeddings para {len(articulos)} artículos de '{fuente_legal}'...")
    # Se embebe título + contenido juntos, no solo contenido: en
    # documentos sin una línea de título real y separada (visto en
    # Decret 32/2005 -- el número va directo al contenido, sin título
    # propio), lo que el parser captura como "título" es en realidad el
    # principio de la primera frase, justo donde suelen estar las
    # palabras clave más relevantes. Sin esto, esas palabras se perdían
    # de la búsqueda semántica por completo.
    embeddings = embed_fn([f"{a.titulo}. {a.contenido}" for a in articulos])

    records = [
        {
            "fuente_legal": fuente_legal,
            "numero_articulo": a.numero_articulo,
            "titulo": a.titulo,
            "contenido": a.contenido,
            "expedient": None,
            "versio": "vigente",
            "zona_pgm": None,  # normativa general, no específica de zona PGM
            "documento_origen": pdf_path.name,
            "embedding": embedding,
        }
        for a, embedding in zip(articulos, embeddings)
    ]

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
    logger.info("Carga de la norma general completada.")
    return count


if __name__ == "__main__":
    configure_logging()
    if len(sys.argv) != 3:
        print('Uso: python -m database.load_general_law <ruta.pdf> "<nombre de la norma>"')
        sys.exit(1)
    run(Path(sys.argv[1]), sys.argv[2])