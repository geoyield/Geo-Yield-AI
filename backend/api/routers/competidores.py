"""
Endpoint de competidores reales, para el mapa del frontend.

Dos modos:
- Sin lat/lon: comportamiento original -- centroide calculado como el
  promedio de todos los competidores del distrito, y hasta `limit` de
  ellos, de los del distrito completo.
- Con lat/lon (cuando el usuario buscó por dirección exacta): centro es
  el punto dado tal cual, y los competidores se buscan por radio real
  alrededor de ese punto (ST_DWithin, en metros) en vez de por distrito
  -- un bar a 400m pero al otro lado de la frontera administrativa del
  distrito sigue siendo competencia real.

No expone las 11.000+ filas de la tabla completa de golpe: se limita el
número de puntos devueltos (parámetro `limit`), tanto por rendimiento
del mapa (Leaflet con miles de marcadores individuales se vuelve lento
e ilegible) como por tamaño de la respuesta HTTP.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.api.deps import get_session
from backend.api.schemas.competidores import CentroOut, CompetidorOut, CompetidoresResponse
from backend.observability import get_logger, log_event

logger = get_logger("api.competidores")

router = APIRouter(prefix="/api", tags=["competidores"])


@router.get("/competidores", response_model=CompetidoresResponse)
def listar_competidores(
    codi_districte: int = Query(..., ge=1, le=10),
    lat: float | None = Query(
        None, description="Si se indica junto con lon, busca por radio alrededor de este punto en vez de todo el distrito."
    ),
    lon: float | None = Query(None),
    radio_metros: int = Query(500, ge=50, le=5000),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_session),
):
    if lat is not None and lon is not None:
        return _buscar_por_radio(db, lat, lon, radio_metros, limit)
    return _buscar_por_distrito(db, codi_districte, limit)


def _buscar_por_distrito(db: Session, codi_districte: int, limit: int) -> CompetidoresResponse:
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


def _buscar_por_radio(db: Session, lat: float, lon: float, radio_metros: int, limit: int) -> CompetidoresResponse:
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