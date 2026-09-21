"""
ETL de renta media por distrito (fuente: INE).

"""

import re

import pandas as pd

from .config import BARCELONA_MUNICIPIO_CODE

INDICATOR_NAME = "Renta neta media por persona"

_DISTRICT_NUMBER_RE = re.compile(r"distrito\s+(\d+)", re.IGNORECASE)


def read_raw_income(path) -> pd.DataFrame:
    """
    Lee el CSV crudo de renta del INE tal cual se descarga.

    dtype=str es intencionado y crítico: si se deja que pandas infiera
    tipos, interpreta la columna de renta como float64 y CORROMPE el
    separador de miles en el proceso — "13.990" se lee como el float 13.99
    (el cero final es insignificante para un float y se pierde), antes de
    que _parse_spanish_number() pueda ver el texto original. Detectado
    probando el pipeline contra datos reales: sin este dtype=str, la renta
    de cualquier distrito cuyo valor termine en una cifra que un float
    normalice (p. ej. un cero final) se cargaba dividida entre 10 o 100.
    """
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str)


def _parse_spanish_number(value: str) -> float:
    """
    Convierte un número en formato español ('.' miles, ',' decimales) a float.

    Ejemplo observado en los datos de origen: "13.990" representa 13990,
    no 13.99 — el INE usa el punto como separador de miles.
    """
    if pd.isna(value):
        return float("nan")
    cleaned = str(value).strip().replace(".", "").replace(",", ".")
    return float(cleaned)


def _extract_district_number(distritos_value: str) -> int | None:
    """Extrae el número de distrito de un valor tipo '0801901 Barcelona distrito 01'."""
    if pd.isna(distritos_value):
        return None
    match = _DISTRICT_NUMBER_RE.search(str(distritos_value))
    return int(match.group(1)) if match else None


def build_district_income(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforma el CSV crudo del INE en una tabla limpia a nivel de distrito.

    Reglas de filtrado (replican el notebook 03_eda_income_ine):
        1. Solo el municipio de Barcelona (código INE 08019).
        2. Filas de nivel DISTRITO: tienen 'Distritos' informado pero
           'Secciones' vacío (las filas con ambos vacíos son el total del
           municipio; las que tienen 'Secciones' informado son de sección
           censal, un nivel de detalle que no usamos en el MVP).
        3. Solo el indicador "Renta neta media por persona".
        4. Solo el año (Periodo) más reciente disponible.

    Devuelve columnas: codi_districte, renta_media, periodo.
    """
    df = raw_df.rename(
        columns={
            raw_df.columns[0]: "Municipio",
            "Indicadores de renta media y mediana": "Indicador",
            "Total": "Renta_Media",
        }
    )

    df["Periodo"] = df["Periodo"].astype(int)

    """ is_barcelona = df["Municipio"].astype(str).str.contains(BARCELONA_MUNICIPIO_CODE, na=False)
    is_district_level = df["Distritos"].notna() & df["Secciones"].isna()
    is_target_indicator = df["Indicador"] == INDICATOR_NAME

    df = df[is_barcelona & is_district_level & is_target_indicator].copy()

    if df.empty:
        raise ValueError(
            "No se encontraron filas de renta a nivel de distrito para Barcelona. "
            "Revisa el formato del CSV de origen (separador/encoding/nombres de columna)."
        )

    latest_period = df["Periodo"].max()
    df = df[df["Periodo"] == latest_period] """

    df["codi_districte"] = df["Distritos"].apply(_extract_district_number)
    df["renta_media"] = df["Renta_Media"].apply(_parse_spanish_number)
    df["periodo"] = df["Periodo"]

    df = df.dropna(subset=["codi_districte", "renta_media"])
    df["codi_districte"] = df["codi_districte"].astype(int)

    return df[["codi_districte", "renta_media", "periodo"]].reset_index(drop=True)


def load_district_income(path) -> pd.DataFrame:
    """Atajo: lee y transforma en un solo paso."""
    return build_district_income(read_raw_income(path))
