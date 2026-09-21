from pydantic import BaseModel, ConfigDict, Field


class GeocodificacionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direccion_encontrada: str
    lat: float
    lon: float
    codi_districte: int | None = Field(
        default=None, description="Distrito sugerido a partir de la dirección, o null si no se pudo determinar."
    )
    zona_pgm: str | None = Field(
        default=None, description="Zona PGM sugerida a partir de las coordenadas, o null si no se pudo determinar."
    )
    clau_urb: str | None = Field(
        default=None,
        description="Código CLAU_URB original del AMB detrás de la zona_pgm sugerida, para transparencia.",
    )