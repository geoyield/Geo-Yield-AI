"""
Chunking de normas generales (BOE, DOGC, y futuras fuentes similares) --
diseñado para generalizar SIN necesitar configuración específica por
documento. Cada fuente nueva que hemos ido incorporando ha traído un
formato ligeramente distinto de las anteriores (NUMAMB, DOGC, BOE...);
en vez de crear un módulo o una bandera de configuración por cada una,
este parser se adapta automáticamente a partir de señales genéricas del
propio texto.

Tres decisiones de diseño, cada una pensada para no depender de qué
documento concreto entre:

1. Encabezado de artículo: una sola expresión regular reconoce tanto
   "Artículo N. Título." (todo en la misma línea, formato BOE) como
   "Artículo N" seguido del título en la línea siguiente (formato DOGC).
   Se decide automáticamente según si hay texto después del número en
   esa misma línea -- no hace falta indicarlo por fuente.

2. Filtrado de índice/tabla de contenidos: los índices reales que hemos
   visto (BOE) usan puntos de relleno ("Artículo 1. Título. . . . . .")
   para alinear con el número de página -- una convención tipográfica
   genérica, no específica de ningún documento. Se descarta cualquier
   encabezado cuyo resto de línea contenga una fila de 5 o más puntos.

3. Cabecera/pie de página: en vez de mantener una lista de frases por
   institución (NUMAMB, DOGC, BOE...), se detectan por FRECUENCIA -- toda
   línea que se repite literalmente 3 o más veces a lo largo del
   documento es, con altísima probabilidad, cabecera o pie de página,
   sea cual sea su contenido concreto. Se complementa con un puñado de
   patrones estructurales genéricos (números de página sueltos, URLs,
   ISSN/DL) que son convención común en publicaciones oficiales
   españolas, no atados a ningún documento en particular.

No sustituye a backend/rag/chunking.py (el parser del PGM/NUMAMB): ese
tiene lógica semánticamente propia (versiones consolidat/modificació/
original apiladas en un mismo PDF, clasificación por zona PGM) que no
aplica a leyes generales, y se mantiene aparte a propósito.
"""

import re
from collections import Counter
from dataclasses import dataclass

_ARTICULO_HEADER_RE = re.compile(
    r"^(?:Article|Artícul[oe])s?\s+(?P<numero>\d+(?:-\d+)?[a-zA-Z]*)\.?\s*(?P<resto>.*)$",
    re.MULTILINE,
)

# 5+ puntos (con o sin espacio entre ellos) -- la firma de un relleno de
# índice, sea cual sea el documento.
_DOT_LEADER_RE = re.compile(r"(?:\.\s?){5,}")

# Patrones estructurales genéricos: convención común en publicaciones
# oficiales españolas (BOE, DOGC...), no atados a un documento concreto.
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
    Quita cualquier línea que se repita 3 o más veces a lo largo del
    texto -- la firma de una cabecera/pie de página, sea cual sea la
    institución que publique el documento. No necesita saber de antemano
    qué dice esa cabecera; la detecta por su propio patrón de repetición.
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
    """
    Parte el texto de una norma general en un ArticuloGeneral por cada
    "Artículo N" real encontrado (las entradas de índice, con puntos de
    relleno, se descartan automáticamente).
    """
    text = clean_boilerplate(text)

    starts = []
    for match in _ARTICULO_HEADER_RE.finditer(text):
        resto = match.group("resto").strip()
        # El título de una entrada de índice puede partirse en varias
        # líneas antes de llegar al relleno de puntos -- en documentos
        # reales se han visto casos de hasta 3 líneas de título antes del
        # relleno (Ley 11/2009, Ley 22/2010). Se usa una ventana generosa
        # (5 líneas / 500 caracteres) en vez de un número ajustado al
        # último caso visto, para no tener que seguir subiéndolo cada vez
        # que aparezca un título todavía más largo.
        tail_lines = text[match.end():match.end() + 500].splitlines()[:5]
        ventana = " ".join([resto, *tail_lines])
        if _DOT_LEADER_RE.search(ventana):
            continue  # entrada de índice/tabla de contenidos, no un artículo real
        starts.append((match.start(), match, resto))

    chunks = []
    for i, (pos, match, resto) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        block = text[match.end():end]

        if resto:
            # Formato "todo en la misma línea" (BOE): el resto de esa
            # línea ES el título; el contenido empieza en la línea siguiente.
            titulo = resto.rstrip(".")
            contenido = block.strip()
        else:
            # Formato "título en la línea siguiente" (DOGC).
            lines = block.strip().splitlines()
            titulo = lines[0].strip() if lines else ""
            contenido = "\n".join(lines[1:]).strip()

        chunks.append(
            ArticuloGeneral(numero_articulo=match.group("numero"), titulo=titulo, contenido=contenido)
        )

    return _dedupe_keeping_longest(chunks)


def _dedupe_keeping_longest(chunks: list[ArticuloGeneral]) -> list[ArticuloGeneral]:
    """
    Red de seguridad: si dos artículos acaban con el mismo numero_articulo
    (ya sea por una entrada de índice que se coló, una numeración de cola
    de documento no anticipada, o cualquier otra rareza del formato de
    origen), se queda con el de CONTENIDO MÁS LARGO -- en todos los casos
    reales vistos hasta ahora, el genuino es sustancialmente más largo que
    la entrada espuria (un índice, tras la limpieza, apenas deja nada).
    Sin esto, un duplicado no anticipado revienta la carga completa en
    Postgres con "ON CONFLICT DO UPDATE command cannot affect row a
    second time".
    """
    mejores: dict[str, ArticuloGeneral] = {}
    for chunk in chunks:
        actual = mejores.get(chunk.numero_articulo)
        if actual is None or len(chunk.contenido) > len(actual.contenido):
            mejores[chunk.numero_articulo] = chunk
    return list(mejores.values())