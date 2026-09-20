"""
Endpoints del agente de viabilidad, para que el frontend pueda pedir
distritos/zonas disponibles y generar el informe completo.

Diseño:
    - Endpoints síncronos (`def`, no `async def`) a propósito: todo el
      pipeline por debajo (SQLAlchemy, sentence-transformers, el cliente
      de Gemini) es síncrono. FastAPI ejecuta los endpoints síncronos en
      un threadpool automáticamente, así que esto no bloquea el bucle de
      eventos -- reescribir todo el pipeline a async sería un cambio de
      arquitectura mucho mayor, sin necesidad real para el volumen de
      peticiones de este MVP.
    - Errores del LLM o de la base de datos se capturan y se traducen a
      un 502 con un mensaje claro, en vez de dejar que FastAPI devuelva
      un stack trace crudo al frontend.
    - /informes/stream entrega la respuesta por Server-Sent Events en vez
      de esperar a tenerla completa -- ver generar_informe_viabilidad_stream.
"""

import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api.deps import get_session
from backend.observability import get_logger
from backend.api.schemas.informes import DistritoOut, InformeRequest, InformeResponse, ZonaPgmOut
from backend.ia.agent import (
    ZONA_PGM_NOMBRES,
    generar_informe_viabilidad,
    generar_informe_viabilidad_stream,
    zonas_pgm_disponibles,
)

logger = get_logger("api.informes")

router = APIRouter(prefix="/api", tags=["informes"])


def _json_default(obj):
    """
    json.dumps no sabe serializar Decimal -- los valores numéricos que
    vienen directos de Postgres (renta_media, opportunity_score...) son
    Decimal, no float, cuando se leen sin pasar por un esquema Pydantic
    (que sí hace esta conversión automáticamente, como en /api/informes
    sin streaming). Aquí, al construir el JSON a mano para cada evento
    SSE, hace falta indicárselo explícitamente.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


@router.get("/distritos", response_model=list[DistritoOut])
def listar_distritos(db: Session = Depends(get_session)):
    rows = db.execute(text("SELECT codi_districte, nom_districte FROM districts ORDER BY codi_districte")).all()
    return [DistritoOut(codi_districte=r.codi_districte, nom_districte=r.nom_districte) for r in rows]


@router.get("/zonas-pgm", response_model=list[ZonaPgmOut])
def listar_zonas_pgm(db: Session = Depends(get_session)):
    """
    Solo devuelve zonas que de verdad tienen normativa cargada (ver
    zonas_pgm_disponibles) -- el desplegable del frontend nunca debe
    ofrecer una opción que vaya a devolver una recuperación vacía.
    """
    zonas = zonas_pgm_disponibles(db)
    return [ZonaPgmOut(id=z, nombre=ZONA_PGM_NOMBRES.get(z, z)) for z in zonas]


@router.post("/informes", response_model=InformeResponse)
def crear_informe(payload: InformeRequest, db: Session = Depends(get_session)):
    try:
        informe = generar_informe_viabilidad(
            db, codi_districte=payload.codi_districte, zona_pgm=payload.zona_pgm
        )
    except Exception:
        # District and zone go in `context`, not interpolated into the
        # message, so Logs Insights can filter on them directly.
        logger.exception(
            "Report generation failed",
            extra={"context": {
                "codi_districte": payload.codi_districte,
                "zona_pgm": payload.zona_pgm,
            }},
        )
        raise HTTPException(
            status_code=502,
            detail="No se pudo generar el informe (fallo al contactar el modelo de IA o la base de datos). Inténtalo de nuevo en unos segundos.",
        )
    return informe


@router.post("/informes/stream")
def crear_informe_stream(payload: InformeRequest, db: Session = Depends(get_session)):
    def eventos():
        try:
            for evento in generar_informe_viabilidad_stream(
                db, codi_districte=payload.codi_districte, zona_pgm=payload.zona_pgm
            ):
                yield f"data: {json.dumps(evento, ensure_ascii=False, default=_json_default)}\n\n"
        except Exception:
            logger.exception(
                "Report streaming failed",
                extra={"context": {
                    "codi_districte": payload.codi_districte,
                    "zona_pgm": payload.zona_pgm,
                }},
            )
            error = {"type": "error", "detail": "No se pudo generar el informe. Inténtalo de nuevo en unos segundos."}
            yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"

    return StreamingResponse(eventos(), media_type="text/event-stream")