"""
==============================================================================
RAG PIPELINE: GENERALIZED LEGAL CHUNKING (NLP)
==============================================================================
File: backend/rag/general_chunking.py

Parses National (BOE) and Regional (DOGC) laws. 
Unlike the PGM parser which is highly specialized, this module is built using 
Heuristics to automatically adapt to new document structures WITHOUT requiring 
hardcoded per-institution configuration rules.
"""

import re
from collections import Counter
from dataclasses import dataclass

# Heuristic 1: Flexible Header Detection
# Matches both "Article 5. Title" (BOE) and "Article 5 \n Title" (DOGC) using a single Regex.
_ARTICULO_HEADER_RE = re.compile(
    r"^(?:Article|Artícul[oe])s?\s+(?P<numero>\d+(?:-\d+)?[a-zA-Z]*)\.?\s*(?P<resto>.*)$",
    re.MULTILINE,
)

# Heuristic 2: Typography Profiling (Table of Contents filtering)
# Detects "dot leaders" (e.g., "Article 1 . . . . . . . 14"), a universal convention 
# in printed PDFs across all institutions, effectively filtering out index pages.
_DOT_LEADER_RE = re.compile(r"(?:\.\s?){5,}")

# Universal Boilerplate Patterns (Page numbers, URLs, ISSNs)
_GENERIC_NOISE_LINE_RES = [
    re.compile(r"^\d{1,6}$"),  # número de página suelto
    re.compile(r"^Página\s+\d+$", re.IGNORECASE),
    re.compile(r"^https?://\S+$"),
    re.compile(r"^ISSN\s+[\d-]+X?$", re.IGNORECASE),
    re.compile(r"^DL\s+[A-Z]-\d+-\d+$"),
]

_MIN_REPETITIONS_FOR_BOILERPLATE = 3
_MAX_BOILERPLATE_LINE_LENGTH = 150


@dataclass
class ArticuloGeneral:
    numero_articulo: str
    titulo: str
    contenido: str


def _strip_repeated_lines(text: str) -> str:
    """
    Heuristic 3: Frequency Analysis for Header/Footer Detection.
    Instead of hardcoding a list of known footers per institution, this algorithm 
    counts line frequencies. Any string that repeats 3+ times in a document is 
    mathematically assumed to be PDF boilerplate and is stripped out.
    """
    lines = text.splitlines()
    counts = Counter(ln.strip() for ln in lines if ln.strip())
    repeated = {
        ln
        for ln, c in counts.items()
        if c >= _MIN_REPETITIONS_FOR_BOILERPLATE and len(ln) <= _MAX_BOILERPLATE_LINE_LENGTH
    }
    return "\n".join(ln for ln in lines if ln.strip() not in repeated)


def clean_boilerplate(text: str) -> str:
    text = text.replace("\f", "\n")
    text = _strip_repeated_lines(text)
    lines = [ln for ln in text.splitlines() if not any(p.match(ln.strip()) for p in _GENERIC_NOISE_LINE_RES)]
    result = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def parse_articulo_general(text: str) -> list[ArticuloGeneral]:
    """Semantic segmentation of general laws (BOE, DOGC)."""
    text = clean_boilerplate(text)

    starts = []
    for match in _ARTICULO_HEADER_RE.finditer(text):
        resto = match.group("resto").strip()

        # We check the next 5 lines to catch long index titles before the dot leader
        tail_lines = text[match.end():match.end() + 500].splitlines()[:5]
        ventana = " ".join([resto, *tail_lines])

        # If we see dot leaders, it's an index entry, not the actual law. Skip it.
        if _DOT_LEADER_RE.search(ventana):
            continue  # entrada de índice/tabla de contenidos, no un artículo real
        starts.append((match.start(), match, resto))

    chunks = []
    for i, (pos, match, resto) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        block = text[match.end():end]

        if resto:
            # Inline Title format (BOE)
            titulo = resto.rstrip(".")
            contenido = block.strip()
        else:
            # Next-line Title format (DOGC)
            lines = block.strip().splitlines()
            titulo = lines[0].strip() if lines else ""
            contenido = "\n".join(lines[1:]).strip()

        chunks.append(
            ArticuloGeneral(numero_articulo=match.group("numero"), titulo=titulo, contenido=contenido)
        )

    return _dedupe_keeping_longest(chunks)


def _dedupe_keeping_longest(chunks: list[ArticuloGeneral]) -> list[ArticuloGeneral]:
    """
    Defensive Programming: Conflict Resolution.
    PDF parsing is inherently messy. If a spurious index entry slips through 
    and shares an ID with the real article, it will crash the Database Upsert 
    ("ON CONFLICT DO UPDATE command cannot affect row a second time"). 
    This acts as a safety net: if two chunks share the same 'numero_articulo', 
    we keep the longest one, assuming it's the actual text and not an index stub.
    """
    mejores: dict[str, ArticuloGeneral] = {}
    for chunk in chunks:
        actual = mejores.get(chunk.numero_articulo)
        if actual is None or len(chunk.contenido) > len(actual.contenido):
            mejores[chunk.numero_articulo] = chunk
    return list(mejores.values())