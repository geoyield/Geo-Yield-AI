"""
==============================================================================
ETL PIPELINE: INGEST NEWLY DISCOVERED PGM ZONES
==============================================================================
File: scripts/investigacion_pgm/load_new_articles.py

Loads the 7 PGM zoning articles identified and verified during this research 
session (304, 305, 306, 307, 308, 309, 313) into the legal corpus, applying 
the exact same schema as the baseline articles (302, 303, 311).

Architectural Notes:
- Article 304 is loaded with `zona_pgm=None` (General Law). Although it was 
  discovered as a cross-reference inside 306, its text regulates general 
  rules for the entire city, not a specific block.
- Articles 307, 308, and 309 share the exact same `zona_pgm` ("edificacio_aillada"). 
  They are subtypes (single-family, multi-family) of the same Clau 20a code. 
  The RAG engine already retrieves multiple articles per zone via vector search, 
  so creating distinct IDs for each subtype would be over-engineering.

Dependency:
Requires `extract_candidates.py` to be executed first to generate the 
`candidatos_para_revisar.json` file.
"""

import json
import os
import re
import sys
from pathlib import Path

# Robust Path Resolution:
# Dynamically resolves the project root regardless of where the developer 
# triggers the script in the terminal, preventing `ModuleNotFoundError`.
project_root = (
    Path.cwd()
    if Path("backend").is_dir()
    else next(parent for parent in Path.cwd().resolve().parents if Path(parent, "backend").is_dir())
)
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("DB_HOST_OVERRIDE", "localhost")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.connection import resolve_database_url
from backend.db.models import LegalChunk
from backend.rag.embeddings import embed_texts

FUENTE = "PGM (Secció V)"

# Hardcoded Article 304: Verified during this session.
# Does not depend on the JSON extraction because it was manually retrieved.
ARTICULO_304 = {
    "titulo": "Usos col·lectius o usos públics en grans superfícies",
    "contenido": (
        "Malgrat el que disposa l'article anterior, es condicionen els usos públics i els usos "
        "col·lectius en superfícies superiors a 10.000m² al fet que la disposició de les "
        "edificacions o instal·lacions, l'ordenació dels volums, la composició estètica, la "
        "destinació de l'edificació o instal·lacions o el trànsit que generin, no trenquin "
        "l'harmonia urbana.\n\n"
        "Quan el projecte no s'adapti a aquestes condicions o per les característiques de "
        "l'edificació, instal·lació o ús no pugui assegurar-se l'harmonia urbana, no s'autoritzaran "
        "aquests usos públics o usos col·lectius en superfícies que depassin els 10.000m²."
    ),
    "zona_pgm": None,
}

# The final mapping decision made after manual review of the candidates
ZONA_PGM_POR_ARTICULO = {
    "305": "conservacio_estructura_urbana",
    "306": "ordenacio_volumetrica_especifica",
    "307": "edificacio_aillada",
    "308": "edificacio_aillada",
    "309": "edificacio_aillada",
    "313": "renovacio_urbana",
}


def limpiar_titulo(titulo: str) -> str:
    """
    Strips the 'Article NNN. ' prefix from the title so it matches the 
    normalized schema format used in the rest of the Vector Database.
    """
    return re.sub(r"^Article\s+\d+\w*\.\s*", "", titulo).strip()


def cargar():
    with open("candidates_for_review.json", encoding="utf-8") as f:
        candidatos = json.load(f)

    articulos_a_insertar = [("304", ARTICULO_304["titulo"], ARTICULO_304["contenido"], ARTICULO_304["zona_pgm"])]

    for numero, zona_pgm in ZONA_PGM_POR_ARTICULO.items():
        if numero not in candidatos:
            print(f"AVISO: Artículo {numero} no está en candidatos_para_revisar.json -- saltando.")
            continue
        titulo = limpiar_titulo(candidatos[numero]["titulo"])
        contenido = candidatos[numero]["contenido"]
        articulos_a_insertar.append((numero, titulo, contenido, zona_pgm))

    engine = create_engine(resolve_database_url())
    insertados = []
    with Session(engine) as session:
        for numero, titulo, contenido, zona_pgm in articulos_a_insertar:
            
            # Idempotency Check: Prevents Primary Key collision crashes
            existe = session.query(LegalChunk).filter_by(fuente_legal=FUENTE, numero_articulo=numero).first()
            if existe:
                print(f"Artículo {numero} ya existe en la base de datos -- saltando (evita duplicados).")
                continue

            embedding = embed_texts([f"{titulo}\n{contenido}"])[0]
            session.add(
                LegalChunk(
                    fuente_legal=FUENTE,
                    numero_articulo=numero,
                    titulo=titulo,
                    contenido=contenido,
                    versio="consolidat",
                    zona_pgm=zona_pgm,
                    embedding=embedding,
                )
            )
            insertados.append(numero)
            print(f"Preparado Artículo {numero} -- zona_pgm={zona_pgm} -- {titulo[:70]}")

        if insertados:
            session.commit()
            print(f"\nInsertados {len(insertados)} artículos nuevos: {', '.join(insertados)}")
        else:
            print("\nNo se insertó ningún artículo nuevo (todos ya existían o faltaban en el JSON).")


if __name__ == "__main__":
    cargar()