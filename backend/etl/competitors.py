"""
ETL de competidores de hostelería y de las tablas de dimensión geográfica
(distritos, barrios), a partir del censo comercial de Barcelona.

Consolida la lógica del notebook `02_eda_census_bcn.ipynb`.
"""

import pandas as pd

# Mismo criterio de filtrado usado en el notebook: por grupo de actividad
# (más fiable) o, si no encaja, por coincidencia de texto en la actividad
# concreta (para capturar variantes que no están bien clasificadas en el
# grupo "Restaurants, bars i hotels").
COMPETITOR_GROUP_KEYWORD = "Restaurants, bars i hotels"
COMPETITOR_ACTIVITY_KEYWORDS = (
    "Restaurants|Bars|CIBERCAFÈ|Degustació|Xocolateries|Geladeries|"
    "Bars especials amb actuació|Bars musicals|Discoteques|PUB"
)

CRITICAL_COLUMNS = ["Codi_Districte", "Nom_Districte", "Latitud", "Longitud", "Nom_Activitat"]

# Los 10 distritos de Barcelona son una lista oficial fija que no cambia.
# BUG DETECTADO PROBANDO EL PIPELINE: derivar `districts` incidentalmente
# de lo que aparezca en el censo comercial es frágil — si una carga puntual
# del censo no cubre algún distrito (por un filtro previo, un extracto
# parcial, etc.), la carga de district_income/district_mobility para ese
# distrito revienta por FK ("insert or update on table district_income
# violates foreign key constraint... Key (codi_districte)=(7) is not
# present in table districts"). Al ser una lista pequeña, cerrada y estable,
# se trata como dato de referencia estático en vez de derivarse de una
# fuente que puede venir incompleta.
BARCELONA_DISTRICTS = {
    1: "Ciutat Vella",
    2: "Eixample",
    3: "Sants-Montjuïc",
    4: "Les Corts",
    5: "Sarrià-Sant Gervasi",
    6: "Gràcia",
    7: "Horta-Guinardó",
    8: "Nou Barris",
    9: "Sant Andreu",
    10: "Sant Martí",
}


def read_raw_census(path) -> pd.DataFrame:
    """
    Lee el CSV crudo del censo comercial de Barcelona.

    encoding="utf-8-sig" es intencionado: el fichero real trae BOM al
    principio (confirmado contra 241021_censcomercialbcn_opendata_2024_v5.csv).
    Sin esto, pandas lee la primera columna como "\ufeffID_Global" en vez de
    "ID_Global", y el filtro de columnas de build_competitors() revienta con
    un KeyError.
    """
    return pd.read_csv(path, low_memory=False, encoding="utf-8-sig")


def build_districts(raw_census_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Devuelve la tabla de dimensión `districts` a partir de la lista de
    referencia estática `BARCELONA_DISTRICTS` (ver nota arriba). El
    parámetro `raw_census_df` se mantiene por compatibilidad de firma con
    el resto del pipeline, pero no se usa como fuente de esta tabla.
    """
    return pd.DataFrame(
        [{"codi_districte": codi, "nom_districte": nom} for codi, nom in BARCELONA_DISTRICTS.items()]
    ).sort_values("codi_districte").reset_index(drop=True)


def build_neighborhoods(raw_census_df: pd.DataFrame) -> pd.DataFrame:
    """Extrae la tabla de dimensión `neighborhoods`, con el mismo criterio que `build_districts`."""
    neighborhoods = (
        raw_census_df[["Codi_Barri", "Nom_Barri", "Codi_Districte"]]
        .dropna()
        .drop_duplicates()
        .rename(
            columns={
                "Codi_Barri": "codi_barri",
                "Nom_Barri": "nom_barri",
                "Codi_Districte": "codi_districte",
            }
        )
    )
    neighborhoods["codi_barri"] = neighborhoods["codi_barri"].astype(int)
    neighborhoods["codi_districte"] = neighborhoods["codi_districte"].astype(int)
    return neighborhoods.sort_values("codi_barri").reset_index(drop=True)


def build_competitors(raw_census_df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra el censo comercial completo a los locales de hostelería
    (competidores), limpia nulos críticos y deja una tabla lista para
    cargar en PostGIS (con Latitud/Longitud, no geometría todavía —
    la conversión a `Geography` se hace en `load_to_db.py`, más cerca de
    la capa de base de datos).
    """
    is_competitor_group = raw_census_df["Nom_Grup_Activitat"].str.contains(
        COMPETITOR_GROUP_KEYWORD, case=False, na=False
    )
    is_competitor_activity = raw_census_df["Nom_Activitat"].str.contains(
        COMPETITOR_ACTIVITY_KEYWORDS, case=False, na=False
    )
    competitors = raw_census_df[is_competitor_group | is_competitor_activity].copy()

    # Se descartan locales sin distrito, coordenadas o actividad: no se
    # pueden geolocalizar ("ghost locations", mismo término usado en el
    # notebook) o violarían el NOT NULL de nom_activitat en el modelo.
    competitors = competitors.dropna(subset=CRITICAL_COLUMNS)

    columns_map = {
        "ID_Global": "id_global",
        "Nom_Local": "nom_local",
        "Nom_Activitat": "nom_activitat",
        "Nom_Grup_Activitat": "nom_grup_activitat",
        "Nom_Sector_Activitat": "nom_sector_activitat",
        "Codi_Barri": "codi_barri",
        "Codi_Districte": "codi_districte",
        "Latitud": "latitud",
        "Longitud": "longitud",
    }
    competitors = competitors[list(columns_map.keys())].rename(columns=columns_map)

    competitors["codi_districte"] = competitors["codi_districte"].astype(int)
    # codi_barri puede venir vacío en algún local suelto: se deja nullable
    # (ver FK nullable en el modelo Competitor) en vez de descartar la fila
    # entera solo por eso.
    competitors["codi_barri"] = competitors["codi_barri"].astype("Int64")

    return competitors.reset_index(drop=True)