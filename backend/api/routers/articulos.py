"""
Endpoint para consultar el texto completo de un artículo legal.

El frontend utiliza este endpoint para resolver las citas incluidas
en los informes de viabilidad.

La identificación se realiza mediante query params porque `fuente_legal`
puede contener caracteres como `/`, `(` y `)`.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api.deps import get_session
from backend.api.schemas.articulos import ArticuloOut
from backend.observability import get_logger, log_event

logger = get_logger("api.articulos")

router = APIRouter(prefix="/api", tags=["articulos"])


@router.get(
    "/articulos",
    response_model=ArticuloOut,
    status_code=status.HTTP_200_OK,
    summary="Obtiene el texto completo de un artículo legal",
    description=(
        "Busca un artículo mediante su fuente legal y número de artículo. "
        "La combinación de ambos valores debe identificar un único artículo."
    ),
)
def obtener_articulo(
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