"""
Bulk ETL job for the Open Data BCN business census.

Pulls the full "Cens de locals i activitat economica" dataset from the CKAN
datastore_search API (paginated), cleans it, and upserts it into the local
Postgres/PostGIS database. Meant to be run periodically (e.g. weekly) rather
than queried live -- see docs/data-sources.md for the rationale.

Usage:
    python ingest_census.py
"""

import logging

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from urllib3.util.retry import Retry

from common import (
    CENSUS_RESOURCE_ID,
    CKAN_BASE_URL,
    CSV_SNAPSHOT_PATH,
    PAGE_SIZE,
    SCHEMA_SQL_PATH,
    get_engine,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ingest_census")

# CKAN field name -> our snake_case column name
COLUMN_MAP = {
    "ID_Global": "id_global",
    "ID_Bcn_2016": "id_bcn_2016",
    "Codi_Principal_Activitat": "codi_principal_activitat",
    "Nom_Principal_Activitat": "nom_principal_activitat",
    "Codi_Sector_Activitat": "codi_sector_activitat",
    "Nom_Sector_Activitat": "nom_sector_activitat",
    "Codi_Grup_Activitat": "codi_grup_activitat",
    "Nom_Grup_Activitat": "nom_grup_activitat",
    "Codi_Activitat_2022": "codi_activitat_2022",
    "Nom_Activitat": "nom_activitat",
    "Codi_Activitat_2016": "codi_activitat_2016",
    "Nom_Local": "nom_local",
    "SN_Oci_Nocturn": "sn_oci_nocturn",
    "SN_Coworking": "sn_coworking",
    "SN_Servei_Degustacio": "sn_servei_degustacio",
    "SN_Obert24h": "sn_obert24h",
    "SN_Mixtura": "sn_mixtura",
    "SN_Carrer": "sn_carrer",
    "SN_Mercat": "sn_mercat",
    "Nom_Mercat": "nom_mercat",
    "SN_Galeria": "sn_galeria",
    "Nom_Galeria": "nom_galeria",
    "SN_CComercial": "sn_ccomercial",
    "Nom_CComercial": "nom_ccomercial",
    "SN_Eix": "sn_eix",
    "Nom_Eix": "nom_eix",
    "X_UTM_ETRS89": "x_utm_etrs89",
    "Y_UTM_ETRS89": "y_utm_etrs89",
    "Latitud": "latitud",
    "Longitud": "longitud",
    "Direccio_Unica": "direccio_unica",
    "Codi_Via": "codi_via",
    "Nom_Via": "nom_via",
    "Planta": "planta",
    "Porta": "porta",
    "Num_Policia_Inicial": "num_policia_inicial",
    "Lletra_Inicial": "lletra_inicial",
    "Num_Policia_Final": "num_policia_final",
    "Lletra_Final": "lletra_final",
    "Solar": "solar",
    "Codi_Parcela": "codi_parcela",
    "Codi_Illa": "codi_illa",
    "Seccio_Censal": "seccio_censal",
    "Codi_Barri": "codi_barri",
    "Nom_Barri": "nom_barri",
    "Codi_Districte": "codi_districte",
    "Nom_Districte": "nom_districte",
    "Referencia_Cadastral": "referencia_cadastral",
    "Data_Revisio": "data_revisio",
}

BOOLEAN_COLUMNS = [
    "sn_oci_nocturn", "sn_coworking", "sn_servei_degustacio", "sn_obert24h",
    "sn_mixtura", "sn_carrer", "sn_mercat", "sn_galeria", "sn_ccomercial", "sn_eix",
]
INTEGER_COLUMNS = [
    "codi_principal_activitat", "codi_sector_activitat", "codi_grup_activitat",
    "codi_activitat_2022", "codi_activitat_2016", "codi_barri", "codi_districte",
]
FLOAT_COLUMNS = ["x_utm_etrs89", "y_utm_etrs89", "latitud", "longitud"]
DATE_COLUMNS = ["data_revisio"]

BATCH_SIZE = 2000


def _session_with_retries() -> requests.Session:
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def fetch_all_records() -> pd.DataFrame:
    """Paginate through CKAN's datastore_search, since it caps rows per response."""
    session = _session_with_retries()
    records = []
    offset = 0

    while True:
        logger.info(f"Fetching records offset={offset} limit={PAGE_SIZE}...")
        response = session.get(
            f"{CKAN_BASE_URL}/datastore_search",
            params={"resource_id": CENSUS_RESOURCE_ID, "limit": PAGE_SIZE, "offset": offset},
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()["result"]
        page = result["records"]
        records.extend(page)

        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    logger.info(f"Fetched {len(records)} total records")
    return pd.DataFrame.from_records(records)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns=["_id"], errors="ignore")
    df = df.rename(columns=COLUMN_MAP)
    df = df[[c for c in COLUMN_MAP.values() if c in df.columns]]

    for col in BOOLEAN_COLUMNS:
        if col in df.columns:
            df[col] = df[col].map({"Si": True, "No": False})

    for col in INTEGER_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in FLOAT_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    df = df.dropna(subset=["id_global"])
    df = df.drop_duplicates(subset=["id_global"])
    return df.where(pd.notnull(df), None)


def ensure_schema(engine) -> None:
    logger.info("Applying database/schema.sql...")
    ddl = SCHEMA_SQL_PATH.read_text()
    with engine.begin() as conn:
        for statement in ddl.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))


def upsert_records(engine, df: pd.DataFrame) -> None:
    from sqlalchemy import MetaData, Table

    metadata = MetaData()
    table = Table("business_census", metadata, autoload_with=engine)
    update_columns = {c.name: c for c in table.c if c.name not in ("id_global", "ingested_at")}

    records = df.to_dict(orient="records")
    with engine.begin() as conn:
        for start in range(0, len(records), BATCH_SIZE):
            batch = records[start:start + BATCH_SIZE]
            stmt = insert(table).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id_global"],
                set_={name: stmt.excluded[name] for name in update_columns},
            )
            conn.execute(stmt)
            logger.info(f"Upserted {min(start + BATCH_SIZE, len(records))}/{len(records)} rows")

        conn.execute(text("""
            UPDATE business_census
            SET geom = ST_SetSRID(ST_MakePoint(longitud, latitud), 4326)
            WHERE latitud IS NOT NULL AND longitud IS NOT NULL
              AND (geom IS NULL OR ST_X(geom) != longitud OR ST_Y(geom) != latitud)
        """))


def main():
    engine = get_engine()
    ensure_schema(engine)

    raw = fetch_all_records()
    df = clean(raw)
    logger.info(f"{len(df)} clean rows ready to load")

    upsert_records(engine, df)

    CSV_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_SNAPSHOT_PATH, index=False)
    logger.info(f"Wrote local snapshot to {CSV_SNAPSHOT_PATH}")

    logger.info("Ingestion complete")


if __name__ == "__main__":
    main()
