"""
==============================================================================
ETL PIPELINE: COMMERCIAL CENSUS & SPATIAL DIMENSIONS
==============================================================================
File: backend/etl/competitors.py

This module extracts the raw commercial census data from Open Data BCN,
cleans it, and builds the DataFrames for the dimensions (Districts, Neighborhoods)
and the main fact table (Competitors). 

It translates the experimental logic from `notebooks/02_eda_census_bcn.ipynb` 
into production-ready ETL functions.
"""

import pandas as pd

# Regular expressions developed during the EDA phase to isolate the target market.
# We filter by group, but also use activity keywords as a fallback to catch
# misclassified businesses in the government dataset.
COMPETITOR_GROUP_KEYWORD = "Restaurants, bars i hotels"
COMPETITOR_ACTIVITY_KEYWORDS = (
    "Restaurants|Bars|CIBERCAFÈ|Degustació|Xocolateries|Geladeries|"
    "Bars especials amb actuació|Bars musicals|Discoteques|PUB"
)

# Mandatory fields required to insert a row into the PostGIS database.
CRITICAL_COLUMNS = ["Codi_Districte", "Nom_Districte", "Latitud", "Longitud", "Nom_Activitat"]

# ------------------------------------------------------------------------------
# ARCHITECTURAL DECISION: STATIC DIMENSION AVOIDING FK VIOLATIONS
# ------------------------------------------------------------------------------
# BUG FIX LOG: Initially, I extracted the 10 districts dynamically from the 
# raw census CSV. However, if a partial or filtered CSV was loaded (e.g., missing 
# District 7 data), the 'districts' table wouldn't create District 7. 
# Consequently, the 'income' and 'mobility' ETLs crashed with a Foreign Key 
# constraint violation when trying to insert data for District 7.
# To ensure referential integrity, static political borders (like the 10 official 
# districts) are now hardcoded as a source of truth.
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
    Reads the raw CSV file.
    
    Data Engineering Note: 
    'utf-8-sig' is strictly required here. The original government CSV file 
    contains a hidden Byte Order Mark (BOM). Standard 'utf-8' reads the first 
    column as '\\ufeffID_Global', which causes a KeyError in the pipeline.
    """
    return pd.read_csv(path, low_memory=False, encoding="utf-8-sig")


def build_districts(raw_census_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Generates the 'districts' dimension table.
    It relies entirely on the hardcoded BARCELONA_DISTRICTS dictionary to 
    prevent missing Foreign Keys in downstream ETLs.
    """
    return pd.DataFrame(
        [{"codi_districte": codi, "nom_districte": nom} for codi, nom in BARCELONA_DISTRICTS.items()]
    ).sort_values("codi_districte").reset_index(drop=True)


def build_neighborhoods(raw_census_df: pd.DataFrame) -> pd.DataFrame:
    """"
    Extracts unique neighborhoods (barrios) dynamically from the census file.
    """
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
    Filters the 68,000+ raw commercial rows down to the relevant hospitality 
    competitors. It drops ghost locations and normalizes column names for PostgreSQL.
    
    Note: Spatial geometry (PostGIS WKTElement) is intentionally NOT handled here.
    It is handled in `load_to_db.py` to keep this ETL strictly focused on Pandas.
    """
    # 1. Apply Regex targeting
    is_competitor_group = raw_census_df["Nom_Grup_Activitat"].str.contains(
        COMPETITOR_GROUP_KEYWORD, case=False, na=False
    )
    is_competitor_activity = raw_census_df["Nom_Activitat"].str.contains(
        COMPETITOR_ACTIVITY_KEYWORDS, case=False, na=False
    )
    competitors = raw_census_df[is_competitor_group | is_competitor_activity].copy()

    # 2. Data Quality Check: Drop rows without spatial coordinates
    competitors = competitors.dropna(subset=CRITICAL_COLUMNS)

    # 3. Rename columns to match the SQLAlchemy ORM model strictly
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

    # Int64 (with capital I) allows nullable integers in Pandas.
    # This prevents the whole row from dropping if a single competitor is missing its neighborhood ID.
    competitors["codi_barri"] = competitors["codi_barri"].astype("Int64")

    return competitors.reset_index(drop=True)