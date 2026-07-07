import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

INGESTION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = INGESTION_DIR.parent

# Overridable via env because the container layout differs from the local repo layout
# (see deployment/docker-compose.yml, where these are bind-mounted under /app).
SCHEMA_SQL_PATH = Path(os.getenv("SCHEMA_SQL_PATH", str(PROJECT_ROOT / "database" / "schema.sql")))
CSV_SNAPSHOT_PATH = Path(os.getenv("CSV_SNAPSHOT_PATH", str(PROJECT_ROOT / "data_raw" / "opendata_bcn" / "comercial.csv")))

# Open Data BCN CKAN instance. Dataset: "Cens de locals i activitat economica"
# https://opendata-ajuntament.barcelona.cat/data/dataset/cens-locals-planta-baixa-act-economica
CKAN_BASE_URL = "https://opendata-ajuntament.barcelona.cat/data/api/3/action"
CENSUS_RESOURCE_ID = "38babeec-5c47-43d3-84e7-b13a4b89004f"
PAGE_SIZE = 5000


def get_engine():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return create_engine(database_url)
