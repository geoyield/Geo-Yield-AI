"""
==============================================================================
ORQUESTADOR DE CARGA ETL (FASE 1)
==============================================================================
Este script actúa como controlador central del pipeline de datos. Extrae los 
archivos brutos (CSV/Excel), aplica las transformaciones de la capa ETL 
(backend/etl/) y materializa los DataFrames resultantes en PostgreSQL/PostGIS.

Uso:
    python -m database.load_to_db

Estrategias de carga híbridas implementadas:
    1. Tablas de dimensión (districts, neighborhoods, income, mobility):
       Se utiliza una estrategia de "Upsert" (INSERT ... ON CONFLICT DO UPDATE).
       Esto permite actualizar valores (ej. un nuevo dato de renta) sin duplicar 
       filas ni borrar la estructura de la base de datos.
    2. Tabla de Censo Comercial (competitors):
       Se utiliza un reemplazo transaccional completo (DELETE + INSERT). 
       Dado que los negocios abren y cierran, un Upsert mantendría negocios 
       "fantasma" que ya no existen en el censo real. El borrado completo 
       garantiza la integridad absoluta con la última foto del ayuntamiento.
"""

import logging

import pandas as pd
from dotenv import load_dotenv
from geoalchemy2.elements import WKTElement
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.db import Base
from backend.db.connection import resolve_database_url
from backend.db.models import Competitor, District, DistrictIncome, DistrictMobility, Neighborhood
from backend.etl import config
from backend.etl.competitors import build_competitors, build_districts, build_neighborhoods, read_raw_census
from backend.etl.income import load_district_income
from backend.etl.mobility import load_district_mobility

logger = logging.getLogger("geoyield_etl")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def _upsert_dataframe(session: Session, model, df: pd.DataFrame, pk_column: str) -> None:
    """
    Función de utilidad para realizar un Upsert masivo (Bulk) nativo en PostgreSQL.
    Traduce un DataFrame de Pandas a una sentencia ON CONFLICT DO UPDATE de SQLAlchemy.
    """
    if df.empty:
        logger.warning(f"DataFrame vacío para {model.__tablename__}, no se carga nada.")
        return

    records = df.to_dict(orient="records")
    stmt = pg_insert(model).values(records)

    # Preparamos el diccionario de columnas a actualizar si hay conflicto de PK
    update_columns = {
        col: getattr(stmt.excluded, col) for col in df.columns if col != pk_column
    }
    stmt = stmt.on_conflict_do_update(index_elements=[pk_column], set_=update_columns)
    session.execute(stmt)
    logger.info(f"{model.__tablename__}: {len(records)} filas upsert-eadas.")


def load_dimensions(session: Session, raw_census_df: pd.DataFrame) -> None:
    """Carga las tablas estáticas (diccionarios geográficos)."""
    districts_df = build_districts(raw_census_df)
    _upsert_dataframe(session, District, districts_df, pk_column="codi_districte")

    neighborhoods_df = build_neighborhoods(raw_census_df)
    _upsert_dataframe(session, Neighborhood, neighborhoods_df, pk_column="codi_barri")


def load_competitors(session: Session, raw_census_df: pd.DataFrame) -> None:
    """Carga el censo de locales utilizando reemplazo completo y tipos PostGIS."""
    competitors_df = build_competitors(raw_census_df)

    # 1. Borrado de la foto anterior (Evita negocios fantasma)
    session.query(Competitor).delete()

    # 2. Reconstrucción con parsing espacial nativo (WKTElement)
    records = []
    for row in competitors_df.itertuples(index=False):
        # Manejo seguro de nulos en foreign keys secundarias
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
                # Conversión de coordenas a formato geográfico estándar (SRID 4326)
                "geom": WKTElement(f"POINT({row.longitud} {row.latitud})", srid=4326),
            }
        )

    if records:
        session.execute(pg_insert(Competitor), records)
    logger.info(f"competitors: {len(records)} filas cargadas (reemplazo completo).")


def load_income(session: Session, path) -> None:
    """Carga datos de métricas de renta (INE)."""
    income_df = load_district_income(path)
    _upsert_dataframe(session, DistrictIncome, income_df, pk_column="codi_districte")


def load_mobility(session: Session, path) -> None:
    """Carga datos de tráfico peatonal (MITMA)."""
    mobility_df = load_district_mobility(path)
    _upsert_dataframe(session, DistrictMobility, mobility_df, pk_column="codi_districte")


def run(engine=None) -> None:
    """Punto de entrada del Orquestador ETL."""
    load_dotenv()

    if engine is None:
        database_url = resolve_database_url()
        engine = create_engine(database_url, future=True)

    logger.info("Cargando censo comercial (dimensiones + competidores)...")
    raw_census_df = read_raw_census(config.PATH_CENSCOMER)

    # El bloque `with` garantiza el manejo de la transacción (Commit o Rollback)
    with Session(engine) as session:
        load_dimensions(session, raw_census_df)

        # Flush fuerza la escritura en BD sin cerrar la transacción.
        # Es obligatorio porque 'competitors' necesita que las PKs de 
        # districts/neighborhoods ya existan para validar sus Foreign Keys.
        session.flush()  

        load_competitors(session, raw_census_df)

        logger.info("Cargando renta media por distrito...")
        load_income(session, config.PATH_INE_RENTA)

        logger.info("Cargando movilidad/afluencia por distrito...")
        load_mobility(session, config.PATH_MITMA_MOBILITY)

        # Si todo el proceso llega hasta aquí sin errores, se consolida la BD.
        session.commit()

    logger.info("Carga completada.")


if __name__ == "__main__":
    run()