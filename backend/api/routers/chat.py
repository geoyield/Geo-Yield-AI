"""
Endpoint del chat conversacional.

No es un agente con herramientas ni memoria: es una traducción de una
frase libre a los mismos parámetros estructurados que el formulario ya
sabe manejar, seguida del pipeline ya existente y probado sin
modificarlo (geocoding.py, amb_identify.py, generar_informe_viabilidad_stream).

Si no se puede resolver dirección, distrito o zona con confianza, el
endpoint NUNCA adivina -- devuelve un evento de aclaración con lo que sí
se pudo determinar, para que el frontend muestre el formulario manual
como red de seguridad, igual que ya hace hoy la búsqueda por dirección.
"""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.api.deps import get_session
from backend.api.routers.informes import _json_default
from backend.api.schemas.chat import ChatRequest
from backend.geo.amb_identify import identificar_zona_pgm
from backend.geo.geocoding import geocodificar_direccion, resolver_distrito_desde_suburb
from backend.ia.agent import generar_informe_viabilidad_stream
from backend.ia.chat_intent import extraer_intencion

logger = logging.getLogger("geoyield_api")

router = APIRouter(prefix="/api", tags=["chat"])


def _evento_aclaracion(mensaje: str, **kwargs) -> dict:
    return {"type": "aclaracion", "mensaje": mensaje, **kwargs}


def _procesar_chat(mensaje: str, db: Session):
    intencion = extraer_intencion(mensaje)
    direccion = intencion["direccion"]
    distrito_mencionado = intencion["distrito_mencionado"]
    pregunta_especifica = intencion["pregunta_especifica"]

    if direccion is None:
        # No hay calle exacta, pero puede que el usuario sí haya dado el
        # distrito -- alguien que conoce la zona general pero no una
        # dirección concreta sigue dando información real y utilizable,
        # aunque no baste para determinar la zona PGM automáticamente
        # (eso requiere coordenadas exactas).
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

        yield _evento_aclaracion(
            "No he podido identificar una dirección ni un distrito de Barcelona en tu mensaje. "
            "¿Puedes indicarme la calle, o al menos en qué distrito te gustaría abrir?"
        )
        return

    geo = geocodificar_direccion(direccion)
    if geo is None:
        yield _evento_aclaracion(
            f"No encontré '{direccion}' dentro de Barcelona. "
            "Puedes revisar la dirección o seleccionar distrito y zona manualmente abajo.",
            direccion_buscada=direccion,
        )
        return

    zona = identificar_zona_pgm(geo["lat"], geo["lon"]) if geo["codi_districte"] else None
    zona_pgm = zona["zona_pgm"] if zona else None

    if geo["codi_districte"] is None or zona_pgm is None:
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

    # Todo resuelto -- se informa la ubicación encontrada antes de
    # empezar a transmitir el informe, para que el frontend pueda
    # mostrar el mapa centrado en el punto exacto de inmediato.
    yield {
        "type": "ubicacion",
        "direccion_encontrada": geo["direccion_encontrada"],
        "lat": geo["lat"],
        "lon": geo["lon"],
        "codi_districte": geo["codi_districte"],
        "zona_pgm": zona_pgm,
    }

    yield from generar_informe_viabilidad_stream(
        db, codi_districte=geo["codi_districte"], zona_pgm=zona_pgm, pregunta_especifica=pregunta_especifica
    )


@router.post("/chat/informe/stream")
def chat_informe_stream(payload: ChatRequest, db: Session = Depends(get_session)):
    def eventos():
        try:
            for evento in _procesar_chat(payload.mensaje, db):
                yield f"data: {json.dumps(evento, ensure_ascii=False, default=_json_default)}\n\n"
        except Exception:
            logger.exception(f"Error procesando el chat para el mensaje: {payload.mensaje!r}")
            error = {"type": "error", "detail": "No se pudo procesar tu mensaje. Inténtalo de nuevo."}
            yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"

    return StreamingResponse(eventos(), media_type="text/event-stream")