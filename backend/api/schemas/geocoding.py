"""
==============================================================================
API SCHEMA: GEOCODING RESPONSE PAYLOAD (DTO)
==============================================================================
File: backend/api/schemas/geocoding.py

Data Transfer Object (DTO) for the geocoding endpoint.
Defines the strict JSON contract expected by the Frontend.
"""

from pydantic import BaseModel, ConfigDict, Field


class GeocodificacionResponse(BaseModel):
    # Security: Prevents internal data leaks if upstream dictionaries contain 
    # extra unmapped fields.
    model_config = ConfigDict(extra="forbid")

    direccion_encontrada: str
    lat: float
    lon: float

    # Graceful Degradation: These fields are explicitly nullable to allow 
    # partial success states if the AI or GIS engine cannot resolve them.
    codi_districte: int | None = Field(
        default=None, description="Distrito sugerido a partir de la dirección, o null si no se pudo determinar."
    )
    zona_pgm: str | None = Field(
        default=None, description="Zona PGM sugerida a partir de las coordenadas, o null si no se pudo determinar."
    )

    # Auditability: Exposing the raw government code alongside our internal mapping.
    clau_urb: str | None = Field(
        default=None,
        description="Código CLAU_URB original del AMB detrás de la zona_pgm sugerida, para transparencia.",
    )