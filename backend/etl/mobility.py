"""
ETL de afluencia peatonal diaria por distrito (fuente: MITMA).

Consolida la lógica del notebook `01_eda_mobility_mitma.ipynb`. El dataset
crudo de MITMA cubre toda España; se filtra a los desplazamientos con
destino en Barcelona y se agregan los viajes por distrito de destino.
"""

import pandas as pd

from .config import BARCELONA_MUNICIPIO_CODE


def read_raw_mobility(path) -> pd.DataFrame:
    """
    Lee el CSV crudo de movilidad de MITMA tal cual se descarga.

    sep="|" es intencionado: MITMA distribuye este fichero con separador
    pipe, no coma (confirmado contra el fichero real
    20251015_Viajes_distritos.csv.gz). pandas.read_csv detecta la
    compresión gzip automáticamente por la extensión .gz, sin parámetros
    adicionales.

    dtype={"destino": str, "origen": str} es intencionado y crítico: sin
    esto, pandas infiere estas columnas como int64 y PIERDE EL CERO INICIAL
    de los códigos de zona ("0801901" se lee como el entero 801901). El
    filtro de prefijo "08019" para Barcelona nunca coincide con un código
    que ya perdió su cero inicial. Mismo patrón de bug que en income.py con
    el separador de miles.
    """
    return pd.read_csv(path, sep="|", dtype={"destino": str, "origen": str}, compression='infer')


def build_district_mobility(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforma el CSV crudo de MITMA en afluencia diaria por distrito.

    El código de zona de destino de MITMA para Barcelona sigue el patrón
    "08" (provincia) + "019" (municipio) + "NN" (distrito, 01-10), p. ej.
    "0801901" para el distrito 1 (Ciutat Vella). Se filtra por ese prefijo
    y se extraen los 2 últimos caracteres como número de distrito.

    Devuelve columnas: codi_districte, daily_foot_traffic, fecha.
    """
    df = raw_df.copy()
    df["destino"] = df["destino"].astype(str)

    is_barcelona = df["destino"].str.startswith(BARCELONA_MUNICIPIO_CODE)
    df = df[is_barcelona].copy()

    if df.empty:
        raise ValueError(
            "No se encontraron desplazamientos con destino en Barcelona. "
            f"Se esperaba que 'destino' empezara por '{BARCELONA_MUNICIPIO_CODE}'; "
            "revisa el formato del CSV de origen de MITMA."
        )

    df["codi_districte"] = df["destino"].str[-2:].astype(int)

    aggregated = (
        df.groupby("codi_districte", as_index=False)
        .agg(daily_foot_traffic=("viajes", "sum"))
    )
    # El dataset de MITMA suele venir para un único día; se toma el primer
    # valor de 'fecha' como referencia informativa (no forma parte de la
    # clave, ver decisión de snapshot único).
    aggregated["fecha"] = pd.to_datetime(df["fecha"].iloc[0], format="%Y%m%d").date()

    return aggregated


def load_district_mobility(path) -> pd.DataFrame:
    """Atajo: lee y transforma en un solo paso."""
    return build_district_mobility(read_raw_mobility(path))