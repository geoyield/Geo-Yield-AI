import requests
from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from . import catastro
from .db import SessionLocal

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/zones")
def list_zones(barcelona_only: bool = True):
    query = "SELECT id, name, is_barcelona FROM zones"
    if barcelona_only:
        query += " WHERE is_barcelona = true"
    query += " ORDER BY id"

    with SessionLocal() as db:
        rows = db.execute(text(query)).mappings().all()
        return [dict(row) for row in rows]


@app.get("/mobility/flows")
def mobility_flows(
    zone_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    hour: int | None = None,
    limit: int = 1000,
):
    conditions = []
    params: dict = {"limit": limit}

    if zone_id:
        conditions.append("(origin_zone_id = :zone_id OR destination_zone_id = :zone_id)")
        params["zone_id"] = zone_id
    if date_from:
        conditions.append("date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("date <= :date_to")
        params["date_to"] = date_to
    if hour is not None:
        conditions.append("hour = :hour")
        params["hour"] = hour

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT date, hour, origin_zone_id, destination_zone_id, trips, trips_km
        FROM mobility_flows_hourly
        {where}
        ORDER BY date, hour
        LIMIT :limit
    """

    with SessionLocal() as db:
        rows = db.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]


@app.get("/mobility/population")
def zone_population(
    zone_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 1000,
):
    conditions = []
    params: dict = {"limit": limit}

    if zone_id:
        conditions.append("zone_id = :zone_id")
        params["zone_id"] = zone_id
    if date_from:
        conditions.append("date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("date <= :date_to")
        params["date_to"] = date_to

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT date, zone_id, people
        FROM zone_population_daily
        {where}
        ORDER BY date
        LIMIT :limit
    """

    with SessionLocal() as db:
        rows = db.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]


@app.get("/neighborhoods")
def list_neighborhoods():
    query = "SELECT neighborhood_code, neighborhood_name, district_code, district_name FROM neighborhoods ORDER BY neighborhood_code"
    with SessionLocal() as db:
        rows = db.execute(text(query)).mappings().all()
        return [dict(row) for row in rows]


@app.get("/competitors")
def list_competitors(
    neighborhood_code: int | None = None,
    activity_group: str | None = None,
    active_only: bool = True,
    limit: int = 1000,
):
    conditions = []
    params: dict = {"limit": limit}

    if neighborhood_code is not None:
        conditions.append("neighborhood_code = :neighborhood_code")
        params["neighborhood_code"] = neighborhood_code
    if activity_group:
        conditions.append("activity_group = :activity_group")
        params["activity_group"] = activity_group
    if active_only:
        conditions.append("activity_status = 'Actiu'")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT id, activity_status, sector, activity_group, activity_name, name, address, lat, lon, neighborhood_code, district_code
        FROM commercial_premises
        {where}
        LIMIT :limit
    """

    with SessionLocal() as db:
        rows = db.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]


@app.get("/demographics/population")
def population_by_neighborhood(neighborhood_code: int | None = None, limit: int = 1000):
    conditions = []
    params: dict = {"limit": limit}

    if neighborhood_code is not None:
        conditions.append("neighborhood_code = :neighborhood_code")
        params["neighborhood_code"] = neighborhood_code

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT reference_date, neighborhood_code, age, sex, people
        FROM population_by_neighborhood
        {where}
        ORDER BY neighborhood_code, age, sex
        LIMIT :limit
    """

    with SessionLocal() as db:
        rows = db.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]


@app.get("/demographics/income")
def income_by_neighborhood(neighborhood_code: int | None = None, limit: int = 1000):
    conditions = []
    params: dict = {"limit": limit}

    if neighborhood_code is not None:
        conditions.append("neighborhood_code = :neighborhood_code")
        params["neighborhood_code"] = neighborhood_code

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT year, neighborhood_code, income_eur_per_capita
        FROM income_by_neighborhood
        {where}
        ORDER BY neighborhood_code
        LIMIT :limit
    """

    with SessionLocal() as db:
        rows = db.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]


@app.get("/points-of-interest")
def list_points_of_interest(category: str | None = None, limit: int = 1000):
    conditions = []
    params: dict = {"limit": limit}

    if category:
        conditions.append("category = :category")
        params["category"] = category

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT osm_type, osm_id, category, name, cuisine, lat, lon
        FROM osm_pois
        {where}
        LIMIT :limit
    """

    with SessionLocal() as db:
        rows = db.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]


@app.get("/catastro/parcel")
def catastro_parcel(lat: float, lon: float):
    """Live lookup against the Sede Electronica del Catastro: cadastral
    reference, building use, total surface area, construction year and
    unit-by-unit breakdown for the parcel at the given coordinates.
    """
    try:
        return catastro.lookup_parcel(lat, lon)
    except catastro.CatastroError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Catastro service error: {e}")
