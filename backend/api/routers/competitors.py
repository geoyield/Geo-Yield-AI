"""
==============================================================================
ROUTER: SPATIAL COMPETITORS ENDPOINT (PHASE 1)
==============================================================================
File: backend/api/routers/competitors.py

This endpoint feeds the interactive map in the frontend.
It implements a hybrid API design with two spatial resolution modes:

1. District Mode: Returns competitors within a political district. The map
   center is calculated on-the-fly as the centroid (geometric average) of
   all premises in that district.
2. Radius Mode: If the user provides coordinates (Lat/Lon) after searching
   for an exact street, we ignore political borders and use PostGIS
   (`ST_DWithin`) to search for real competition within a radius in meters.

Performance Lesson (Full-Stack):
We do not expose the >11,000 rows of the commercial census at once. We force a
`limit` parameter because, during development, I discovered that rendering
thousands of Leaflet markers simultaneously crashed the browser's DOM.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api.deps import get_session
from backend.api.schemas.competitors import CentroOut, CompetidorOut, CompetidoresResponse
from backend.observability import get_logger, log_event

logger = get_logger("api.competidores")

router = APIRouter(prefix="/api", tags=["competitors"])


@router.get("/competitors", response_model=CompetidoresResponse)
def list_competitors(
    codi_districte: int = Query(..., ge=1, le=10),
    lat: float | None = Query(
        None, description="If provided alongside lon, searches by radius around this point instead of the whole district."
    ),
    lon: float | None = Query(None),
    radio_metros: int = Query(500, ge=50, le=5000),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_session),
):
    # Smart routing: the frontend doesn't need to send a explicit "mode" flag.
    # The mere presence of coordinates triggers the geometric search.
    if lat is not None and lon is not None:
        return _search_by_radius(db, lat, lon, radio_metros, limit)
    return _search_by_district(db, codi_districte, limit)


def _search_by_district(db: Session, codi_districte: int, limit: int) -> CompetidoresResponse:
    # Dynamic SQL: We calculate the map camera's centroid on the fly.
    # We extract X and Y using native PostGIS functions.
    centro_row = db.execute(
        text(
            """
            SELECT AVG(ST_Y(geom::geometry)) AS lat, AVG(ST_X(geom::geometry)) AS lng, COUNT(*) AS total
            FROM competitors
            WHERE codi_districte = :codi
            """
        ),
        {"codi": codi_districte},
    ).mappings().first()

    if centro_row is None or centro_row["total"] == 0:
        # A district with no competitors loaded is a data gap, not a normal
        # result: the map silently renders empty for the user.
        log_event(
            logger, "WARNING", "No competitors found for district",
            event="competidores.vacio", codi_districte=codi_districte,
        )
        return CompetidoresResponse(centro=None, total=0, competidores=[], modo="distrito")

    filas = db.execute(
        text(
            """
            SELECT id_global, nom_activitat, ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng
            FROM competitors
            WHERE codi_districte = :codi
            LIMIT :limit
            """
        ),
        {"codi": codi_districte, "limit": limit},
    ).mappings().all()

    return CompetidoresResponse(
        centro=CentroOut(lat=centro_row["lat"], lng=centro_row["lng"]),
        total=centro_row["total"],
        competidores=[CompetidorOut(**dict(f)) for f in filas],
        modo="distrito",
    )


def _search_by_radius(db: Session, lat: float, lon: float, radio_metros: int, limit: int) -> CompetidoresResponse:
    punto = f"POINT({lon} {lat})"

    total_row = db.execute(
        text("SELECT COUNT(*) AS total FROM competitors WHERE ST_DWithin(geom, ST_GeogFromText(:punto), :radio)"),
        {"punto": punto, "radio": radio_metros},
    ).mappings().first()
    total = total_row["total"] if total_row else 0

    filas = db.execute(
        text(
            """
            SELECT id_global, nom_activitat, ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng
            FROM competitors
            WHERE ST_DWithin(geom, ST_GeogFromText(:punto), :radio)
            LIMIT :limit
            """
        ),
        {"punto": punto, "radio": radio_metros, "limit": limit},
    ).mappings().all()

    return CompetidoresResponse(
        centro=CentroOut(lat=lat, lng=lon),
        total=total,
        competidores=[CompetidorOut(**dict(f)) for f in filas],
        modo="radio",
        radio_metros=radio_metros,
    )