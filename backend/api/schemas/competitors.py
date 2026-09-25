"""
==============================================================================
RESPONSE SCHEMAS (PYDANTIC DTOs) - COMPETITORS
==============================================================================
File: backend/api/schemas/competitors.py

These schemas act as Data Transfer Objects (DTOs). Their function is to filter 
and shape the data coming from the database (SQLAlchemy) before converting it 
into a JSON payload for the frontend.

Architectural Lesson: 
We must never return the raw database model directly through the API. Doing so 
would expose internal details (such as timestamps or the PostGIS binary format) 
to the client. By using Pydantic, we ensure that we only send the latitude and 
longitude in a format (float) that the Vue/Leaflet map natively understands, 
thereby saving bandwidth and enforcing a strict API contract.
"""
from pydantic import BaseModel


class CentroOut(BaseModel):
    lat: float
    lng: float


class CompetidorOut(BaseModel):
    id_global: str
    nom_activitat: str
    lat: float
    lng: float


class CompetidoresResponse(BaseModel):
    centro: CentroOut | None
    total: int
    competidores: list[CompetidorOut]
    modo: str  # "distrito" (centroid + whole district) or "radio" (exact point + radius in meters)
    radio_metros: int | None = None