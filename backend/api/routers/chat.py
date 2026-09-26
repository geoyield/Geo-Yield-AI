"""
==============================================================================
API ROUTER: CONVERSATIONAL AGENT ORCHESTRATOR (SSE)
==============================================================================
File: backend/api/routers/chat.py

The master endpoint for the conversational chat (`/api/chat/informe/stream`).
Acts as a State Machine connecting NLU, GIS, and RAG into a single SSE stream.

Architectural Note:
This is NOT an autonomous agent. It translates free text into structured parameters 
and routes them through the pre-existing, tested pipeline. 
It strictly enforces Human-in-the-Loop: If intent or geolocation cannot be resolved 
with certainty, it yields an 'aclaracion' event to trigger the manual UI form, 
never guessing.
"""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.api.deps import get_session
from backend.api.routers.reports import _json_default
from backend.api.schemas.chat import ChatRequest
from backend.geo.amb_identify import identificar_zona_pgm
from backend.geo.geocoding import geocodificar_direccion, resolver_distrito_desde_suburb
from backend.ia.agent import generar_informe_viabilidad_stream
from backend.ia.chat_intent import extraer_intencion

logger = logging.getLogger("geoyield_api")

router = APIRouter(prefix="/api", tags=["chat"])


def _evento_aclaracion(mensaje: str, **kwargs) -> dict:
    """Helper to construct standard fallback events for the UI."""
    return {"type": "aclaracion", "mensaje": mensaje, **kwargs}


def _procesar_chat(mensaje: str, db: Session):
    """
    Generator function representing the State Machine of the conversational flow.
    """
    # ------------------------------------------------------------------------
    # STEP 1: Natural Language Understanding (NLU)
    # ------------------------------------------------------------------------
    intencion = extraer_intencion(mensaje)
    direccion = intencion["direccion"]
    distrito_mencionado = intencion["distrito_mencionado"]
    pregunta_especifica = intencion["pregunta_especifica"]

    if direccion is None:
        # Fallback 1A: User gave a general district but no address ("I know Les Corts...")
        if distrito_mencionado is not None:
            codi_districte = resolver_distrito_desde_suburb(distrito_mencionado)
            if codi_districte is not None:
                yield _evento_aclaracion(
                    f"Localicé el distrito de {distrito_mencionado}, pero sin una dirección exacta "
                    "no puedo determinar automáticamente la zona urbanística -- selecciónala tú abajo "
                    "para generar el informe.",
                    codi_districte=codi_districte,
                )
                return

        # Fallback 1B: Complete NLU Failure (No location found)
        yield _evento_aclaracion(
            "No he podido identificar una dirección ni un distrito de Barcelona en tu mensaje. "
            "¿Puedes indicarme la calle, o al menos en qué distrito te gustaría abrir?"
        )
        return

    # ------------------------------------------------------------------------
    # STEP 2: Geospatial Pipeline (Text to Lat/Lon -> PGM Zone)
    # ------------------------------------------------------------------------
    geo = geocodificar_direccion(direccion)
    if geo is None:
        # Fallback 2: Address not found by Nominatim
        yield _evento_aclaracion(
            f"No encontré '{direccion}' dentro de Barcelona. "
            "Puedes revisar la dirección o seleccionar distrito y zona manualmente abajo.",
            direccion_buscada=direccion,
        )
        return

    zona = identificar_zona_pgm(geo["lat"], geo["lon"]) if geo["codi_districte"] else None
    zona_pgm = zona["zona_pgm"] if zona else None

    if geo["codi_districte"] is None or zona_pgm is None:
        # Fallback 3: Graceful Degradation (Found Lat/Lon, but GIS failed)
        yield _evento_aclaracion(
            "Encontré la dirección, pero no pude determinar "
            + ("el distrito" if geo["codi_districte"] is None else "la zona urbanística")
            + " con precisión. Complétalo tú abajo para generar el informe.",
            direccion_encontrada=geo["direccion_encontrada"],
            lat=geo["lat"],
            lon=geo["lon"],
            codi_districte=geo["codi_districte"],
            zona_pgm=zona_pgm,
        )
        return

    # ------------------------------------------------------------------------
    # STEP 3: RAG Pre-Flight Event (UI Synchronization)
    # ------------------------------------------------------------------------
    # Yields the location to the Frontend immediately so the Map can pan/zoom
    # while the heavy LLM RAG engine boots up.
    yield {
        "type": "ubicacion",
        "direccion_encontrada": geo["direccion_encontrada"],
        "lat": geo["lat"],
        "lon": geo["lon"],
        "codi_districte": geo["codi_districte"],
        "zona_pgm": zona_pgm,
    }

    # ------------------------------------------------------------------------
    # STEP 4: RAG Legal Assessment (Streaming)
    # ------------------------------------------------------------------------
    yield from generar_informe_viabilidad_stream(
        db, codi_districte=geo["codi_districte"], zona_pgm=zona_pgm, pregunta_especifica=pregunta_especifica
    )


@router.post("/chat/informe/stream")
def chat_informe_stream(payload: ChatRequest, db: Session = Depends(get_session)):
    """SSE Endpoint. Serializes the generator chunks into standard SSE format."""
    def eventos():
        try:
            for evento in _procesar_chat(payload.mensaje, db):
                # Reuses _json_default from informes.py to handle Decimal database types
                yield f"data: {json.dumps(evento, ensure_ascii=False, default=_json_default)}\n\n"
        except Exception:
            logger.exception(f"Error procesando el chat para el mensaje: {payload.mensaje!r}")
            error = {"type": "error", "detail": "No se pudo procesar tu mensaje. Inténtalo de nuevo."}
            yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"

    return StreamingResponse(eventos(), media_type="text/event-stream")