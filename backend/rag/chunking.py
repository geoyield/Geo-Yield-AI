"""
==============================================================================
RAG PIPELINE: LEGAL DOCUMENT CHUNKING (PGM BARCELONA)
==============================================================================
File: backend/rag/chunking.py

This module handles the semantic segmentation (chunking) of the Barcelona 
General Metropolitan Plan (PGM) legal texts extracted from PDFs.

Critical Design Constraints:
Government PDFs append multiple historical versions of the same article 
(Consolidated, Partial Modification, Original 1985) in a single document. 
This script implements strict version-control logic to ensure the RAG system 
only embeds the currently valid (Consolidated) law, preventing the LLM 
from citing repealed regulations.
"""

import re
from dataclasses import dataclass
from enum import Enum

# Regex to capture the Article Number, Qualifier (e.g., 'consolidat'), and Title
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

# ------------------------------------------------------------------------------
# DOMAIN KNOWLEDGE MAPPING
# ------------------------------------------------------------------------------
# Static mapping of PGM Articles (Section V) to Urban Zones.
# Similar to the Districts mapping in the ETL phase, these legal zone 
# definitions are stable facts of the domain, not dynamic configurations.
ARTICLE_TO_ZONA_PGM = {
    "302": "nucli_antic",
    "303": "densificacio_urbana",
    "311": "industrial",
}

# Regex patterns to strip useless PDF UI artifacts (headers, footers, URLs)
_PDF_BOILERPLATE_LINE_RES = [
    re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}$"),
    re.compile(r"^Índex normes urbanístiques.*Àrea Metropolitana de Barcelona$"),
    re.compile(r"^https://www\.amb\.cat/.*index-normes-urbanistiques$"),
    re.compile(r"^\d+/\d+$"),
    re.compile(r"^Amplia apartat únic$"),
]


class VersioArticle(Enum):
    """Enumeration to track the legal status of an extracted text block."""
    CONSOLIDAT = "consolidat"
    ORIGINAL = "original"
    MODIFICACIO_PARCIAL = "modificacio_parcial"


@dataclass
class LegalChunk:
    """Data Transfer Object (DTO) for a parsed legal article segment."""
    numero_articulo: str
    titulo: str
    contenido: str
    expedient: str | None
    versio: VersioArticle


def clean_pdf_text(text: str) -> str:
    """
    Strips repeating PDF headers, footers, and pagination artifacts.
    This must be done BEFORE parsing to prevent boilerplate text from 
    breaking the Regex boundaries or polluting the semantic embeddings.
    """
    text = text.replace("\f", "\n")
    lines = text.splitlines()
    cleaned = [ln for ln in lines if not any(pat.match(ln.strip()) for pat in _PDF_BOILERPLATE_LINE_RES)]
    result = "\n".join(cleaned)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def _find_article_starts(text: str) -> list[tuple[int, re.Match, str]]:
    """
    Locates the precise starting index of an article and reconstructs its full title.

    Bug Fix Note (Multiline Titles):
    Long legal titles often break across multiple lines in the PDF. 
    Initially, checking only the immediate next line caused valid 'Consolidated' 
    articles to be silently dropped. The logic now tolerates up to 3 continuation 
    lines to successfully capture long titles without losing the anchor.
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
                break  
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
        # Remove internal portal boilerplate
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
    Resolves legal versioning conflicts within the parsed document.
    
    If the PDF stacked multiple historical versions of the same article, 
    this function strictly filters out outdated text. It prioritizes the 
    CONSOLIDATED (currently valid) version. It completely discards Partial 
    Modifications because they are incomplete text fragments (e.g., missing 
    paragraphs replaced with '[...]') which would degrade the LLM's context.
    """
    by_article: dict[str, list[LegalChunk]] = {}
    for chunk in chunks:
        by_article.setdefault(chunk.numero_articulo, []).append(chunk)

    selected = []
    for numero, versions in by_article.items():
        consolidat = next((c for c in versions if c.versio == VersioArticle.CONSOLIDAT), None)
        original = next((c for c in versions if c.versio == VersioArticle.ORIGINAL), None)
        # Fallback to original ONLY if consolidated does not exist
        chosen = consolidat or original
        if chosen is not None:
            selected.append(chosen)
    return selected
