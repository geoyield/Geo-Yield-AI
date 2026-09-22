"""
Esquemas de entrada/salida del endpoint de informes de viabilidad
(backend/api/routers/informes.py).
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Semaforo(str, Enum):
    """Veredicto final de viabilidad -- coincide con lo que garantiza
    _parsear_semaforo_y_resumen() en backend/ia/agent.py."""

    VERDE = "verde"
    AMBAR = "ambar"
    ROJO = "rojo"


class InformeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codi_districte: int = Field(..., ge=1, le=10, description="Código del distrito de Barcelona (1-10)")
    # zona_pgm se deja como str, no como Enum cerrado a propósito: las
    # zonas válidas se leen dinámicamente de la base de datos (ver
    # zonas_pgm_disponibles() en agent.py), no de una lista fija en el
    # código -- un Enum aquí rechazaría zonas nuevas aunque ya tuvieran
    # normativa cargada, hasta que alguien recuerde actualizar este
    # fichero también.
    zona_pgm: str = Field(..., min_length=1, description="Zona urbanística del PGM -- ver GET /api/zonas-pgm")


class DatosDistrito(BaseModel):
    """
    Todos los campos son opcionales a propósito: cuando el distrito
    pedido no tiene datos en district_scorecard, generar_informe_viabilidad()
    devuelve un diccionario vacío en vez de fallar -- este esquema debe
    poder representar ese caso sin reventar la validación.
    """

    model_config = ConfigDict(extra="forbid")

    codi_districte: int | None = None
    nom_districte: str | None = None
    daily_foot_traffic: float | None = None
    renta_media: float | None = None
    total_competitors: int | None = None
    opportunity_score: float | None = None


class ArticuloCitadoOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numero_articulo: str
    fuente_legal: str


class InformeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semaforo: Semaforo
    resumen: str
    datos_distrito: DatosDistrito
    respuesta_legal: str
    articulos_citados: list[ArticuloCitadoOut] = Field(default_factory=list)


class DistritoOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codi_districte: int
    nom_districte: str


class ZonaPgmOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    nombre: str