"""
==============================================================================
DATA WRANGLING: STAGING & CANDIDATE EXTRACTION
==============================================================================
File: scripts/investigacion_pgm/extract_candidates.py

Extracts the full text of the candidate zoning articles identified during the 
research phase (305, 306, 307, 308, 309, 313), utilizing the actual field names 
confirmed from the API (not the official documentation).

Architectural Note (Human-in-the-Loop):
This script intentionally DOES NOT assign `zona_pgm` or write to the database. 
It acts as an ETL Staging Area. It extracts and cleans the text, saving it to 
an intermediate JSON file (`candidatos_para_revisar.json`). A human expert must 
review the content before deciding the final `zona_pgm` classification.
"""

import json
import re

# Candidate articles identified by title, pending manual content verification.
ARTICULOS_CANDIDATOS = {
    "305": "clau 15 -- Conservació de l'estructura urbana i edificatòria",
    "306": "clau 18 -- Ordenació volumètrica específica",
    "307": "clau 20a (subzones unifamiliars) -- Ordenació en edificació aïllada",
    "308": "clau 20a (subzones plurifamiliars I-IV) -- Ordenació en edificació aïllada",
    "309": "clau 20a (subzona plurifamiliar V) -- Ordenació en edificació aïllada",
    "313": "clau 17/6 -- Renovació urbana",
}


def limpiar_html(texto: str) -> str:
    """
    Data Sanitization: 
    Strips raw HTML tags while preserving structural line breaks (<br>/<li>). 
    Feeding raw HTML into an NLP Embedding Model degrades semantic search quality.
    """
    if not texto:
        return ""
    texto = re.sub(r"<br\s*/?>", "\n", texto)
    texto = re.sub(r"</li>", "\n", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = texto.replace("&nbsp;", " ").replace("&amp;", "&")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def extraer_candidatos():
    with open("raw_response.json", encoding="utf-8") as f:
        data = json.load(f)

    encontrados = {}
    for item in data["items"]:
        numero = item.get("numeroArticle")
        if numero in ARTICULOS_CANDIDATOS:
            titulo = item.get("titol", {}).get("ca_ES", "")
            contenido = limpiar_html(item.get("description", {}).get("ca_ES", ""))
            encontrados[numero] = {"titulo": titulo, "contenido": contenido}

    # Data Quality Check: Alert if expected candidates are missing in the payload
    faltantes = set(ARTICULOS_CANDIDATOS) - set(encontrados)
    if faltantes:
        print(f"AVISO: no se encontraron estos artículos en la respuesta: {faltantes}")

    # Staging Area Output
    with open("candidatos_para_revisar.json", "w", encoding="utf-8") as f:
        json.dump(encontrados, f, ensure_ascii=False, indent=2)

    print(f"Extraídos {len(encontrados)} de {len(ARTICULOS_CANDIDATOS)} candidatos.")
    print("Guardado también en candidatos_para_revisar.json.\n")

    for numero, info in encontrados.items():
        print("=" * 70)
        print(f"Artículo {numero} -- candidato para {ARTICULOS_CANDIDATOS[numero]}")
        print(f"Título real: {info['titulo']}")
        print("=" * 70)
        print(info["contenido"])
        print()


if __name__ == "__main__":
    extraer_candidatos()