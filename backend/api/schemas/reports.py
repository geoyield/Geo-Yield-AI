"""
==============================================================================
API SCHEMAS (DTO): VIABILITY REPORTS
==============================================================================
File: backend/api/schemas/informes.py

Defines the Data Transfer Objects (DTOs) for the Viability Report endpoints.
Uses Pydantic for strict input/output validation, acting as the boundary 
between the AI backend and the Frontend UI.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Semaforo(str, Enum):
    """
    Final Business Verdict.
    This enum matches the strict guarantee provided by `_parsear_semaforo_y_resumen()` 
    in `backend/ia/agent.py`. By locking this down as an Enum, we prevent the 
    API from sending hallucinated verdicts (e.g., 'AZUL') to the frontend if 
    the LLM misbehaves.
    """
    VERDE = "verde"
    AMBAR = "ambar"
    ROJO = "rojo"


class InformeRequest(BaseModel):
    # Security: Forbid unexpected fields to prevent Mass Assignment vulnerabilities
    model_config = ConfigDict(extra="forbid")

    codi_districte: int = Field(..., ge=1, le=10, description="Código del distrito de Barcelona (1-10)")

    # Architectural Note: Dynamic vs Static Typing
    # `zona_pgm` is intentionally left as a raw string, NOT a closed Enum.
    # The list of valid zones is dynamic, growing as we ingest more PDFs into 
    # the database (see `zonas_pgm_disponibles()` in agent.py). 
    # If this were an Enum, updating the database with a new law would require 
    # an API code redeployment just to update the Enum list. A raw string 
    # decouples the API schema from the database content.
    zona_pgm: str = Field(..., min_length=1, description="Zona urbanística del PGM -- ver GET /api/zonas-pgm")


class DatosDistrito(BaseModel):
    """
    Demographic and Spatial Metrics (Phase 1 Data).
    
    Resilience Design:
    All fields are intentionally `Optional` (`| None = None`). If a district 
    is missing from the `district_scorecard` view due to a data ingestion error, 
    the AI Agent gracefully returns an empty dictionary. If these fields were 
    required, Pydantic would throw a fatal 500 Validation Error, crashing 
    the entire report. Optionality allows the Legal RAG part of the report 
    to still be delivered to the user even if the GIS data is missing.
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
    # Enforce an empty list instead of null if no articles are cited
    articulos_citados: list[ArticuloCitadoOut] = Field(default_factory=list)


class DistritoOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codi_districte: int
    nom_districte: str


class ZonaPgmOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    nombre: str