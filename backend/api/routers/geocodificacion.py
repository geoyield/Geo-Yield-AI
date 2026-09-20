"""
Endpoint que combina geocodificación de direcciones (Nominatim) con
identificación de zona PGM (servicio Identify del AMB), para sugerir
distrito y zona a partir de una dirección de texto libre.

Nunca falla del todo si una de las dos fuentes no responde: si Nominatim
no encuentra la dirección, es un 404 real (no hay nada que sugerir).
Pero si el AMB no responde o no reconoce la zona, se devuelve igualmente
el distrito ya resuelto, con zona_pgm=null -- la sugerencia parcial
sigue siendo útil, no hace falta todo o nada.
"""

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.schemas.geocodificacion import GeocodificacionResponse
from backend.geo.amb_identify import identificar_zona_pgm
from backend.geo.geocoding import geocodificar_direccion
from backend.observability import get_logger, log_event

logger = get_logger("api.geocodificacion")

router = APIRouter(prefix="/api", tags=["geocodificacion"])


@router.get("/geocodificar", response_model=GeocodificacionResponse)
def geocodificar(direccion: str = Query(..., min_length=3)):
    resultado_geo = geocodificar_direccion(direccion)
    if resultado_geo is None:
        # GDPR: the address the user typed is personal data and is never
        # logged -- only the fact that it did not resolve.
        log_event(logger, "WARNING", "Address could not be geocoded",
                  event="direccion.no_encontrada")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se pudo encontrar esa dirección dentro de Barcelona.",
        )

    resultado_zona = identificar_zona_pgm(resultado_geo["lat"], resultado_geo["lon"])
    if resultado_zona is None:
        log_event(
            logger, "WARNING", "Address geocoded but PGM zone could not be determined",
            event="zona_pgm.no_determinada",
            codi_districte=resultado_geo["codi_districte"],
        )

    return GeocodificacionResponse(
        direccion_encontrada=resultado_geo["direccion_encontrada"],
        lat=resultado_geo["lat"],
        lon=resultado_geo["lon"],
        codi_districte=resultado_geo["codi_districte"],
        zona_pgm=resultado_zona["zona_pgm"] if resultado_zona else None,
        clau_urb=resultado_zona["clau_urb"] if resultado_zona else None,
    )