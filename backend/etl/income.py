"""
==============================================================================
ETL PIPELINE: DISTRICT INCOME (INE)
==============================================================================
File: backend/etl/income.py

This module extracts and transforms district-level income data from the Spanish 
National Statistics Institute (INE). It implements the logic prototyped in the 
Jupyter Notebook '03_eda_income_ine.ipynb'.
"""

import re

import pandas as pd

from .config import BARCELONA_MUNICIPIO_CODE

INDICATOR_NAME = "Renta neta media por persona"

# Pre-compile the regex for performance: extracts digits following the word "distrito"
_DISTRICT_NUMBER_RE = re.compile(r"distrito\s+(\d+)", re.IGNORECASE)


def read_raw_income(path) -> pd.DataFrame:
    """
    Reads the raw INE income CSV file.

    Data Engineering Note (Defensive Programming):
    `dtype=str` is strictly required here to prevent silent data corruption. 
    The INE provides numbers in Spanish format (e.g., "13.990" means 13,990 Euros).
    If we let Pandas infer the types, it reads the dot as a decimal separator,
    converting the string to a float (13.99). Since 13.990 and 13.99 are 
    mathematically identical in Python, the trailing zero is lost forever, making 
    it impossible to reconstruct the original number. By forcing `dtype=str`, 
    we capture the raw text before Pandas tries to "be smart".
    """
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str)


def _parse_spanish_number(value: str) -> float:
    """
    Safely converts a Spanish-localized string number into a Python float.
    Spanish format: '.' for thousands, ',' for decimals.
    Example: "13.990,50" -> 13990.50
    """
    if pd.isna(value):
        return float("nan")
    cleaned = str(value).strip().replace(".", "").replace(",", ".")
    return float(cleaned)


def _extract_district_number(distritos_value: str) -> int | None:
    """
    Uses Regex to extract the clean integer ID from a dirty government string.
    Example: "0801901 Barcelona distrito 01" -> 1
    """
    if pd.isna(distritos_value):
        return None
    match = _DISTRICT_NUMBER_RE.search(str(distritos_value))
    return int(match.group(1)) if match else None


def build_district_income(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms the raw INE DataFrame into a clean, district-level fact table.
    
    Transformation Rules (Derived from EDA phase):
        1. Filter by target municipality (Barcelona INE code '08019').
        2. Isolate DISTRICT level granularity (has 'Distritos', but no 'Secciones').
        3. Filter by the specific target indicator.
        4. Retain only the most recent available year (Periodo).
    """
    df = raw_df.rename(
        columns={
            raw_df.columns[0]: "Municipio",
            "Indicadores de renta media y mediana": "Indicador",
            "Total": "Renta_Media",
        }
    )

    df["Periodo"] = df["Periodo"].astype(int)

    # 1. Geographic & Indicator Filtering
    is_barcelona = df["Municipio"].astype(str).str.contains(BARCELONA_MUNICIPIO_CODE, na=False)
    # Boolean logic to isolate the exact level of granularity (Districts)
    is_district_level = df["Distritos"].notna() & df["Secciones"].isna()
    is_target_indicator = df["Indicador"] == INDICATOR_NAME

    df = df[is_barcelona & is_district_level & is_target_indicator].copy()

    if df.empty:
        raise ValueError(
            "No income rows found for Barcelona districts."
            "Verify the source CSV format (separator/encoding/column names)."
        )

    latest_period = df["Periodo"].max()
    df = df[df["Periodo"] == latest_period]

    df["codi_districte"] = df["Distritos"].apply(_extract_district_number)
    df["renta_media"] = df["Renta_Media"].apply(_parse_spanish_number)
    df["periodo"] = df["Periodo"]

    df = df.dropna(subset=["codi_districte", "renta_media"])
    df["codi_districte"] = df["codi_districte"].astype(int)

    return df[["codi_districte", "renta_media", "periodo"]].reset_index(drop=True)


def load_district_income(path) -> pd.DataFrame:
    """Wrapper function: Reads and transforms the dataset in a single call."""
    return build_district_income(read_raw_income(path))
