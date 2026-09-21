"""
Chunking de normativa legal (Reglament del PGM de Barcelona, portal NUMAMB).

Dos formatos de origen posibles, ambos soportados:

1. Copy-paste de la página web (varios artículos distintos seguidos), donde
   cada artículo va seguido de un botón "Descarregar".
2. Exportación a PDF de un único artículo ("Imprimir -> Guardar como PDF"
   desde el navegador), que NO incluye "Descarregar" (es un botón de UI, no
   se imprime) y en su lugar trae la metadata (Expedient/Darrera
   modificació) justo debajo del título. Cada PDF de este tipo apila,
   además, las distintas VERSIONES HISTÓRICAS del mismo artículo: la
   consolidada (vigente), la del último expediente de modificación (solo el
   fragmento que cambió, con "[...]" donde no hubo cambios) y la original
   de 1985. Solo la vigente nos sirve para el RAG — mezclar las tres
   arriesga que el motor cite normativa derogada.

   El PDF también añade cabecera/pie de página repetidos en cada hoja
   (fecha de impresión, título de la web, URL, "página X/Y") que hay que
   limpiar antes de parsear los artículos.
"""

import re
from dataclasses import dataclass
from enum import Enum

_ARTICLE_HEADER_RE = re.compile(
    r"^Article\s+(?P<numero>\d+[a-z]*)"
    r"(?:\s*\((?P<qualificador>consolidat|modifica(?:ci[oó])?\s*\d*)\)?)?"
    r"\.\s*(?P<titulo>.+?)\s*$",
    re.MULTILINE,
)

_METADATA_RE = re.compile(r"^(Expedient|Darrera modificació):\s*(.+)$", re.MULTILINE)

_ARTICLE_REFERENCE_LINE_RE = re.compile(
    r"^Article\s+\d+[a-z]*(?:\s*\([^)]*\)?)?\.\s*.+$"
)

# Mapeo artículo -> zona PGM (Article 314, Capítol 4: "Qualificacions
# zonals"). Los artículos de la Secció V (302-313) son la lista canónica y
# estable de zonas del PGM -- mismo patrón que BARCELONA_DISTRICTS en
# backend/etl/competitors.py: un hecho del dominio que no cambia, no una
# configuración. Se amplía según se ingieran más artículos de esa sección;
# no hace falta anticipar aquí las zonas que todavía no están cargadas.
ARTICLE_TO_ZONA_PGM = {
    "302": "nucli_antic",
    "303": "densificacio_urbana",
    "311": "industrial",
}

_PDF_BOILERPLATE_LINE_RES = [
    re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}$"),
    re.compile(r"^Índex normes urbanístiques.*Àrea Metropolitana de Barcelona$"),
    re.compile(r"^https://www\.amb\.cat/.*index-normes-urbanistiques$"),
    re.compile(r"^\d+/\d+$"),
    re.compile(r"^Amplia apartat únic$"),
]


class VersioArticle(Enum):
    CONSOLIDAT = "consolidat"
    ORIGINAL = "original"
    MODIFICACIO_PARCIAL = "modificacio_parcial"


@dataclass
class LegalChunk:
    numero_articulo: str
    titulo: str
    contenido: str
    expedient: str | None
    versio: VersioArticle


def clean_pdf_text(text: str) -> str:
    """Quita la cabecera/pie de página repetidos en cada hoja del PDF y el form feed."""
    text = text.replace("\f", "\n")
    lines = text.splitlines()
    cleaned = [ln for ln in lines if not any(pat.match(ln.strip()) for pat in _PDF_BOILERPLATE_LINE_RES)]
    result = "\n".join(cleaned)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def _find_article_starts(text: str) -> list[tuple[int, re.Match, str]]:
    """
    Localiza los inicios reales de artículo y reconstruye el título completo.

    Los títulos largos se parten en varias líneas al extraer el PDF (p. ej.
    "Article 302 (consolidat. Zona de nucli antic: de substitució de\\n
    l'edificació antiga..."). Comprobar solo la primera línea siguiente para
    encontrar el ancla ('Descarregar' o metadata) hacía que estos artículos
    se descartaran en silencio — grave porque justo eran las versiones
    CONSOLIDADAS (vigentes) las que tenían títulos largos con qualificador,
    y el código se quedaba solo con la versión original (desactualizada).
    Se admite un margen de hasta 3 líneas de continuación del título antes
    de dar por buena o descartada la coincidencia.
    """
    starts = []
    for match in _ARTICLE_HEADER_RE.finditer(text):
        tail = text[match.end():match.end() + 500]
        continuation_lines = []
        for line in tail.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped == "Descarregar" or _METADATA_RE.match(stripped):
                full_title = " ".join([match.group("titulo").strip(), *continuation_lines]).strip()
                starts.append((match.start(), match, full_title))
                break
            continuation_lines.append(stripped)
            if len(continuation_lines) > 3:
                break  # demasiadas líneas sin ancla: no es un inicio de artículo real
    return starts


def _determine_versio(qualificador: str | None) -> VersioArticle:
    if qualificador and "consolidat" in qualificador:
        return VersioArticle.CONSOLIDAT
    if qualificador and "modifica" in qualificador:
        return VersioArticle.MODIFICACIO_PARCIAL
    return VersioArticle.ORIGINAL


def _strip_trailing_navigation_lines(content: str) -> str:
    lines = content.splitlines()
    while lines and (not lines[-1].strip() or _ARTICLE_REFERENCE_LINE_RE.match(lines[-1].strip())):
        lines.pop()
    return "\n".join(lines).strip()


def parse_legal_chunks(text: str) -> list[LegalChunk]:
    text = clean_pdf_text(text)
    starts = _find_article_starts(text)
    chunks = []

    for i, (pos, match, full_title) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        block = text[pos:end]

        meta_match = _METADATA_RE.search(block)
        expedient = meta_match.group(2).strip() if meta_match else None

        content_start = meta_match.end() if meta_match else match.end()
        content = block[content_start:]
        content = content.replace(
            "Text consolidat que incorpora les modificacions dels expedients anteriors", ""
        )
        content = re.sub(r"\bLlegir més\s*$", "", content.strip())
        content = _strip_trailing_navigation_lines(content)

        chunks.append(
            LegalChunk(
                numero_articulo=match.group("numero"),
                titulo=full_title,
                contenido=content,
                expedient=expedient,
                versio=_determine_versio(match.group("qualificador")),
            )
        )

    return chunks


def select_current_versions(chunks: list[LegalChunk]) -> list[LegalChunk]:
    """
    Cuando un mismo artículo aparece varias veces (típico en los PDF, que
    apilan consolidada + modificación parcial + original), se queda con UNA
    sola versión por artículo: la consolidada si existe, si no la original.
    La versión "modificació parcial" NUNCA se selecciona: es un fragmento
    incompleto (con "[...]" donde no hubo cambios), no un texto legal
    autocontenido, y además ya está incorporada en la consolidada.
    """
    by_article: dict[str, list[LegalChunk]] = {}
    for chunk in chunks:
        by_article.setdefault(chunk.numero_articulo, []).append(chunk)

    selected = []
    for numero, versions in by_article.items():
        consolidat = next((c for c in versions if c.versio == VersioArticle.CONSOLIDAT), None)
        original = next((c for c in versions if c.versio == VersioArticle.ORIGINAL), None)
        chosen = consolidat or original
        if chosen is not None:
            selected.append(chosen)
    return selected
