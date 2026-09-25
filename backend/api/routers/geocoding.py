"""
==============================================================================
API ROUTER: GEOCODING & SPATIAL INTERSECTION
==============================================================================
File: backend/api/routers/geocoding.py

Endpoint that combines free-text geocoding (Nominatim) with spatial intersection 
(AMB Identify Service) to suggest both the District and the PGM Urban Zone.

Graceful Degradation Design:
The endpoint avoids an "all-or-nothing" failure state. 
- If Nominatim fails to find the address, it raises a hard HTTP 404 (True failure).
- If Nominatim succeeds but the AMB service fails (or returns an unmapped zone), 
  it returns an HTTP 200 with the District resolved and `zona_pgm=null`. This 
  partial payload allows the frontend to pre-fill half the form instead of 
  crashing entirely.
"""

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.schemas.geocoding import GeocodificacionResponse
from backend.geo.amb_identify import identificar_zona_pgm
from backend.geo.geocoding import geocodificar_direccion

router = APIRouter(prefix="/api", tags=["geocodificacion"])


@router.get("/geocode", response_model=GeocodificacionResponse)
def geocodificar(direccion: str = Query(..., min_length=3)):
    # Step 1: Text-to-Coordinates (Nominatim)
    resultado_geo = geocodificar_direccion(direccion)
    if resultado_geo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se pudo encontrar esa dirección dentro de Barcelona.",
        )

    # Step 2: Point-in-Polygon (AMB Identify)
    # This acts as a pipeline, piping the Lat/Lon from Step 1 into Step 2.
    resultado_zona = identificar_zona_pgm(resultado_geo["lat"], resultado_geo["lon"])

    # Step 3: Payload Construction (Partial Failure Tolerance)
    return GeocodificacionResponse(
        direccion_encontrada=resultado_geo["direccion_encontrada"],
        lat=resultado_geo["lat"],
        lon=resultado_geo["lon"],
        codi_districte=resultado_geo["codi_districte"],
        zona_pgm=resultado_zona["zona_pgm"] if resultado_zona else None,
        clau_urb=resultado_zona["clau_urb"] if resultado_zona else None,
    )