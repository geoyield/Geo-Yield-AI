"""
Configuración de rutas del pipeline ETL.
"""

from pathlib import Path

# backend/etl/config.py -> backend/etl -> backend -> raíz del repo
REPO_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = REPO_ROOT / "data" / "processed"

# Ficheros de origen esperados (ver docs/data-sources.md para el origen de
# cada uno). Los nombres de fichero concretos pueden ajustarse aquí sin
# tocar la lógica de transformación en income.py/mobility.py/competitors.py.
# Ficheros de origen esperados (ver docs/data-sources.md para el origen de
# cada uno). Nombres reales tal como los provee cada fuente (MITMA, Open
# Data BCN, INE) — no se renombran, para poder reemplazarlos sin fricción
# cuando lleguen nuevas descargas con el mismo patrón de nombre.
PATH_CENSCOMER = RAW_DATA_DIR / "241021_censcomercialbcn_opendata_2024_v5.csv"
#PATH_INE_RENTA = RAW_DATA_DIR / "30896.csv"
PATH_INE_RENTA = RAW_DATA_DIR / "quina_merda.csv"
# .csv.gz: MITMA lo distribuye comprimido. pandas.read_csv detecta la
# compresión gzip automáticamente por la extensión, sin parámetros extra.
PATH_MITMA_MOBILITY = RAW_DATA_DIR / "20250601_Viajes_distritos_bcnc.csv"

# Código INE del municipio de Barcelona (provincia 08 + municipio 019).
# Toda la lógica de filtrado geográfico de la Fase 1 gira en torno a este
# valor, ya que el MVP se centra en una única ciudad piloto.
BARCELONA_MUNICIPIO_CODE = "08019"