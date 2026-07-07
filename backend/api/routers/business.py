import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select

from ..schemas.business import BusinessListResponse, BusinessOut, DensityBucket, DensityResponse

logger = logging.getLogger("geoyield_api")

router = APIRouter(prefix="/businesses", tags=["businesses"])

GROUP_BY_COLUMNS = {
    "districte": ("codi_districte", "nom_districte"),
    "barri": ("codi_barri", "nom_barri"),
}


def _get_table(request: Request):
    table = getattr(request.app.state, "business_table", None)
    if table is None:
        raise HTTPException(status_code=503, detail="Business data not available yet")
    return table


def _apply_filters(
    query,
    table,
    codi_districte: Optional[int],
    codi_barri: Optional[int],
    nom_activitat: Optional[str],
    q: Optional[str],
    min_lat: Optional[float],
    max_lat: Optional[float],
    min_lon: Optional[float],
    max_lon: Optional[float],
):
    if codi_districte is not None:
        query = query.where(table.c.codi_districte == codi_districte)
    if codi_barri is not None:
        query = query.where(table.c.codi_barri == codi_barri)
    if nom_activitat is not None:
        query = query.where(table.c.nom_activitat.ilike(f"%{nom_activitat}%"))
    if q is not None:
        like = f"%{q}%"
        query = query.where((table.c.nom_local.ilike(like)) | (table.c.nom_activitat.ilike(like)))
    if min_lat is not None:
        query = query.where(table.c.latitud >= min_lat)
    if max_lat is not None:
        query = query.where(table.c.latitud <= max_lat)
    if min_lon is not None:
        query = query.where(table.c.longitud >= min_lon)
    if max_lon is not None:
        query = query.where(table.c.longitud <= max_lon)
    return query


@router.get("", response_model=BusinessListResponse)
def list_businesses(
    request: Request,
    codi_districte: Optional[int] = None,
    codi_barri: Optional[int] = None,
    nom_activitat: Optional[str] = None,
    q: Optional[str] = None,
    min_lat: Optional[float] = None,
    max_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lon: Optional[float] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    table = _get_table(request)
    engine = request.app.state.db_engine

    base_filters = dict(
        codi_districte=codi_districte, codi_barri=codi_barri, nom_activitat=nom_activitat, q=q,
        min_lat=min_lat, max_lat=max_lat, min_lon=min_lon, max_lon=max_lon,
    )

    count_query = _apply_filters(select(func.count()).select_from(table), table, **base_filters)
    list_query = _apply_filters(select(table), table, **base_filters).limit(limit).offset(offset)

    with engine.connect() as conn:
        total = conn.execute(count_query).scalar_one()
        rows = conn.execute(list_query).mappings().all()

    return BusinessListResponse(
        total=total,
        limit=limit,
        offset=offset,
        results=[BusinessOut.model_validate(dict(row)) for row in rows],
    )


@router.get("/density", response_model=DensityResponse)
def business_density(
    request: Request,
    group_by: str = Query("districte", pattern="^(districte|barri)$"),
    nom_activitat: Optional[str] = None,
):
    table = _get_table(request)
    engine = request.app.state.db_engine
    code_col, name_col = GROUP_BY_COLUMNS[group_by]

    query = select(
        table.c[code_col].label("group_key"),
        func.max(table.c[name_col]).label("group_label"),
        func.count().label("business_count"),
    ).group_by(table.c[code_col]).order_by(func.count().desc())

    if nom_activitat is not None:
        query = query.where(table.c.nom_activitat.ilike(f"%{nom_activitat}%"))

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    return DensityResponse(
        group_by=group_by,
        activity_filter=nom_activitat,
        buckets=[
            DensityBucket(
                group_key=str(row["group_key"]) if row["group_key"] is not None else "unknown",
                group_label=row["group_label"],
                business_count=row["business_count"],
            )
            for row in rows
        ],
    )


@router.get("/geojson")
def businesses_geojson(
    request: Request,
    codi_districte: Optional[int] = None,
    codi_barri: Optional[int] = None,
    nom_activitat: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(1000, ge=1, le=5000),
):
    table = _get_table(request)
    engine = request.app.state.db_engine

    query = _apply_filters(
        select(table), table,
        codi_districte=codi_districte, codi_barri=codi_barri, nom_activitat=nom_activitat, q=q,
        min_lat=None, max_lat=None, min_lon=None, max_lon=None,
    ).where(table.c.latitud.is_not(None)).where(table.c.longitud.is_not(None)).limit(limit)

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["longitud"], row["latitud"]]},
            "properties": {
                "id_global": row["id_global"],
                "nom_local": row["nom_local"],
                "nom_activitat": row["nom_activitat"],
                "nom_barri": row["nom_barri"],
                "nom_districte": row["nom_districte"],
            },
        }
        for row in rows
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/{id_global}", response_model=BusinessOut)
def get_business(request: Request, id_global: str):
    table = _get_table(request)
    engine = request.app.state.db_engine

    with engine.connect() as conn:
        row = conn.execute(select(table).where(table.c.id_global == id_global)).mappings().first()

    if row is None:
        raise HTTPException(status_code=404, detail="Business not found")
    return BusinessOut.model_validate(dict(row))
