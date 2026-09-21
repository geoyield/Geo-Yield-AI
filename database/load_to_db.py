"""
Orquestador de carga: ejecuta el ETL (backend/etl/) y escribe
el resultado en Postgres/PostGIS.

Uso:
    python -m database.load_to_db

Estrategia de carga (snapshot único, decisión validada con el usuario):
    - districts / neighborhoods: upsert (INSERT ... ON CONFLICT DO UPDATE),
      ya que son tablas de dimensión que rara vez cambian.
    - district_income / district_mobility: upsert por codi_districte — cada
      ejecución sobrescribe el valor anterior en vez de acumular histórico.
    - competitors: reemplazo transaccional completo (DELETE + INSERT). Los
      negocios abren y cierran, así que un upsert por id_global dejaría
      "fantasmas" de locales que ya no existen; un reemplazo completo es
      más correcto para este caso que un upsert selectivo.
"""
import logging

import pandas as pd
from dotenv import load_dotenv
from geoalchemy2.elements import WKTElement
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

import sys
sys.path.insert(0, '/home/claud/pontia/PJ')

from backend.db import Base
from backend.db.connection import resolve_database_url
from backend.db.models import Competitor, District, DistrictIncome, DistrictMobility, Neighborhood
from backend.etl import config
from backend.etl.competitors import build_competitors, build_districts, build_neighborhoods, read_raw_census
from backend.etl.income import load_district_income
from backend.etl.mobility import load_district_mobility

from backend.observability import configure_logging, get_logger

logger = get_logger("etl.load_to_db")


def _upsert_dataframe(session: Session, model, df: pd.DataFrame, pk_column: str) -> None:
    """Upsert genérico: inserta o actualiza fila a fila por clave primaria."""
    if df.empty:
        logger.warning(f"DataFrame vacío para {model.__tablename__}, no se carga nada.")
        return

    records = df.to_dict(orient="records")
    stmt = pg_insert(model).values(records)
    update_columns = {
        col: getattr(stmt.excluded, col) for col in df.columns if col != pk_column
    }
    stmt = stmt.on_conflict_do_update(index_elements=[pk_column], set_=update_columns)
    session.execute(stmt)
    logger.info(f"{model.__tablename__}: {len(records)} filas upsert-eadas.")


def load_dimensions(session: Session, raw_census_df: pd.DataFrame) -> None:
    districts_df = build_districts(raw_census_df)
    _upsert_dataframe(session, District, districts_df, pk_column="codi_districte")

    neighborhoods_df = build_neighborhoods(raw_census_df)
    _upsert_dataframe(session, Neighborhood, neighborhoods_df, pk_column="codi_barri")


def load_competitors(session: Session, raw_census_df: pd.DataFrame) -> None:
    competitors_df = build_competitors(raw_census_df)

    session.query(Competitor).delete()

    records = []
    for row in competitors_df.itertuples(index=False):
        codi_barri = None if pd.isna(row.codi_barri) else int(row.codi_barri)
        records.append(
            {
                "id_global": row.id_global,
                "nom_local": row.nom_local,
                "nom_activitat": row.nom_activitat,
                "nom_grup_activitat": row.nom_grup_activitat,
                "nom_sector_activitat": row.nom_sector_activitat,
                "codi_barri": codi_barri,
                "codi_districte": row.codi_districte,
                "geom": WKTElement(f"POINT({row.longitud} {row.latitud})", srid=4326),
            }
        )

    if records:
        session.execute(pg_insert(Competitor), records)
    logger.info(f"competitors: {len(records)} filas cargadas (reemplazo completo).")


def load_income(session: Session, path) -> None:
    income_df = load_district_income(path)
    _upsert_dataframe(session, DistrictIncome, income_df, pk_column="codi_districte")


def load_mobility(session: Session, path) -> None:
    mobility_df = load_district_mobility(path)
    _upsert_dataframe(session, DistrictMobility, mobility_df, pk_column="codi_districte")


def run(engine=None) -> None:
    load_dotenv()

    if engine is None:
        database_url = resolve_database_url()
        engine = create_engine(database_url, future=True)

    logger.info("Cargando censo comercial (dimensiones + competidores)...")
    raw_census_df = read_raw_census(config.PATH_CENSCOMER)

    with Session(engine) as session:
        load_dimensions(session, raw_census_df)
        session.flush()  # districts/neighborhoods deben existir antes de las FKs de competitors
        load_competitors(session, raw_census_df)

        logger.info("Cargando renta media por distrito...")
        load_income(session, config.PATH_INE_RENTA)

        logger.info("Cargando movilidad/afluencia por distrito...")
        load_mobility(session, config.PATH_MITMA_MOBILITY)

        session.commit()

    logger.info("Carga completada.")


if __name__ == "__main__":
    configure_logging()
    run()