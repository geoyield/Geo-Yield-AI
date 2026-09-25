"""
==============================================================================
DATA WRANGLING: MISSING ZONES & CROSS-REFERENCES
==============================================================================
File: scripts/investigacion_pgm/find_pending.py

Continuation of `extract_candidates.py`:

1. Fetches Article 304 (a cross-reference cited inside Article 306).
2. Searches across ALL articles (not just 'Títol IV') for any title mentioning 
   "desenvolupament" (development). The GIS keys 19, 20b, and 22b did not appear 
   in the expected chapter, but they might be regulated elsewhere in the PGM.

Note: This script does not assign `zona_pgm` or load anything into the database. 
It only searches and displays the data so the developer can read the actual 
content and make a decision.
"""

import json
import re


def limpiar_html(texto: str) -> str:
    """
    Data Sanitization:
    Government APIs often return text polluted with raw HTML tags instead of 
    pure JSON strings. This function strips tags and decodes HTML entities 
    to make the text readable for manual review.
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


def main():
    # Load the raw JSON payload downloaded in step 1 (diagnostico_amb.py)
    with open("raw_response.json", encoding="utf-8") as f:
        data = json.load(f)

    items = data["items"]

    # 1. Artículo 304 (referencia cruzada del 306)
    # RAG Completeness: If Article 306 relies on rules defined in 304, 
    # the AI will hallucinate if 304 is missing from the Vector Database.
    print("=" * 70)
    print("ARTÍCULO 304 (referencia cruzada citada en el 306)")
    print("=" * 70)
    encontrado_304 = False
    for item in items:
        if item.get("numeroArticle") == "304":
            encontrado_304 = True
            print(f"Título real: {item.get('titol', {}).get('ca_ES', '')}")
            print()
            print(limpiar_html(item.get("description", {}).get("ca_ES", "")))
    if not encontrado_304:
        print("No se encontró el Artículo 304 en la respuesta.")

    # 2. Búsqueda ampliada de "desenvolupament" en TODOS los 574 artículos,
    #    no solo los del Títol IV -- para 19, 20b, 22b.
    # Exhaustive Search: Don't assume data lives where it "should" live.
    print()
    print("=" * 70)
    print("BÚSQUEDA AMPLIADA: 'desenvolupament' en TODOS los artículos")
    print("=" * 70)
    candidatos = []
    for item in items:
        titulo = item.get("titol", {}).get("ca_ES", "")
        if "desenvolupament" in titulo.lower():
            seccion = item.get("titolNormativa", [{}])[0].get("label", {}).get("ca_ES", "?")
            candidatos.append((item.get("numeroArticle"), titulo, seccion))

    if not candidatos:
        print("Ningún artículo, en todo el PGM, menciona 'desenvolupament' en su título.")
    else:
        for numero, titulo, seccion in candidatos:
            print(f"Art. {numero} -- {titulo}  [sección: {seccion}]")


if __name__ == "__main__":
    main()