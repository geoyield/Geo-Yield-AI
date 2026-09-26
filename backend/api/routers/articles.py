"""
==============================================================================
API ROUTER: LEGAL ARTICLE RETRIEVAL (UI VIEWER)
==============================================================================
File: backend/api/routers/articles.py

Endpoint used by the Vue Frontend to fetch the raw text of a specific legal
article. This powers the "Verify Source" side-panel, allowing users to cross-check
the LLM's citations against the original law.

Architectural Design Note (Query vs Path Parameters):
We explicitly use Query Params instead of Path Params here.
A legal source name often contains slashes or parentheses (e.g., 'Ordre INT/358/2011').
If we mapped this as a Path Param (`/api/articulos/Ordre INT/358/2011/4`), the
HTTP router would break, misinterpreting the slash as a new nested route.
Query params (`?fuente_legal=...`) natively handle URL-encoding of special characters.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api.deps import get_session
from backend.api.schemas.articles import ArticuloOut
from backend.observability import get_logger, log_event

logger = get_logger("api.articulos")

router = APIRouter(prefix="/api", tags=["articulos"])


@router.get(
    "/articles",
    response_model=ArticuloOut,
    status_code=status.HTTP_200_OK,
    summary="Obtiene el texto completo de un artículo legal",
    description=(
        "Busca un artículo mediante su fuente legal y número de artículo. "
        "La combinación de ambos valores debe identificar un único artículo."
    ),
)
def obtener_articulo(
    # Use FastAPI Query() to enforce presence and add OpenAPI documentation
    fuente_legal: str = Query(
        ...,
        min_length=1,
        description="Nombre exacto de la fuente legal.",
    ),
    numero_articulo: str = Query(
        ...,
        min_length=1,
        description="Número exacto del artículo.",
    ),
    db: Session = Depends(get_session),
) -> ArticuloOut:
    fuente = fuente_legal.strip()
    numero = numero_articulo.strip()

    if not fuente or not numero:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="fuente_legal y numero_articulo no pueden estar vacíos.",
        )

    # We use a raw SQL query here for speed and simplicity, matching the composite key
    row = db.execute(
        text(
            """
            SELECT
                fuente_legal,
                numero_articulo,
                titulo,
                contenido
            FROM legal_chunks
            WHERE fuente_legal = :fuente
              AND numero_articulo = :numero
            """
        ),
        {
            "fuente": fuente,
            "numero": numero,
        },
    ).mappings().first()

    if row is None:
        # An article cited by a report that cannot then be retrieved points to
        # a hallucinated citation or a stale legal corpus, so it is worth a
        # signal rather than a silent 404.
        log_event(
            logger, "WARNING", "Cited legal article not found",
            event="articulo.no_encontrado", fuente_legal=fuente, numero_articulo=numero,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró ese artículo.",
        )

    return ArticuloOut(
        fuente_legal=row["fuente_legal"],
        numero_articulo=row["numero_articulo"],
        titulo=row["titulo"],
        contenido=row["contenido"],
    )