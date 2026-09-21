"""
Extracción de texto de los PDF de normativa (un artículo por PDF, exportado
desde el navegador del portal NUMAMB — ver backend/rag/chunking.py para el
formato exacto).

Se usa `pdftotext` (poppler-utils) en modo simple, sin -layout: es el modo
que se validó contra los 3 PDF reales del usuario (Article_302/303/311) y
preserva el salto de línea de los títulos largos de forma consistente con
lo que espera el chunker.
"""

import subprocess
from pathlib import Path


def extract_text_from_pdf(path: Path) -> str:
    """
    Extrae el texto de un PDF con pdftotext.

    Lanza RuntimeError con la salida de stderr si pdftotext falla (p. ej.
    PDF corrupto o poppler-utils no instalado), en vez de dejar que
    subprocess.CalledProcessError se propague sin contexto legible.
    """
    result = subprocess.run(
        ["pdftotext", str(path), "-"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext falló al procesar {path}: {result.stderr.strip()}")
    return result.stdout
