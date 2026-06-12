#!/usr/bin/env python3
"""Load Open Data BCN files from data_raw/opendata_bcn/ into Postgres.

Usage:
    python load_opendata_bcn.py

Each table is a full snapshot (not daily incremental files like MITMA), so
every run truncates and reloads the corresponding tables.
"""

import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from common import DATA_RAW_DIR

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/geoyield"
)

SRC_DIR = DATA_RAW_DIR / "opendata_bcn"


def load_neighborhoods(conn, comercial: pd.DataFrame, poblacio: pd.DataFrame) -> None:
    neighborhoods_a = comercial[["Codi_Barri", "Nom_Barri", "Codi_Districte", "Nom_Districte"]]
    neighborhoods_b = poblacio[["Codi_Barri", "Nom_Barri", "Codi_Districte", "Nom_Districte"]]
    neighborhoods = pd.concat([neighborhoods_a, neighborhoods_b], ignore_index=True).drop_duplicates(
        subset=["Codi_Barri"]
    )

    rows = [
        (int(r.Codi_Barri), r.Nom_Barri, int(r.Codi_Districte), r.Nom_Districte)
        for r in neighborhoods.itertuples()
    ]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE neighborhoods")
        execute_values(
            cur,
            "INSERT INTO neighborhoods (neighborhood_code, neighborhood_name, district_code, district_name) VALUES %s",
            rows,
        )
    conn.commit()
    print(f"neighborhoods: {len(rows)} rows")


def load_commercial_premises(conn, df: pd.DataFrame) -> None:
    cols = [
        "ID_Global",
        "Nom_Principal_Activitat",
        "Nom_Sector_Activitat",
        "Nom_Grup_Activitat",
        "Nom_Activitat",
        "Nom_Local",
        "Direccio_Unica",
        "Latitud",
        "Longitud",
        "Codi_Barri",
        "Codi_Districte",
    ]
    df = df[cols].copy()
    df["Latitud"] = pd.to_numeric(df["Latitud"], errors="coerce")
    df["Longitud"] = pd.to_numeric(df["Longitud"], errors="coerce")
    df["Codi_Barri"] = pd.to_numeric(df["Codi_Barri"], errors="coerce")
    df["Codi_Districte"] = pd.to_numeric(df["Codi_Districte"], errors="coerce")

    rows = [
        (
            r.ID_Global,
            r.Nom_Principal_Activitat,
            r.Nom_Sector_Activitat,
            r.Nom_Grup_Activitat,
            r.Nom_Activitat,
            r.Nom_Local,
            r.Direccio_Unica,
            None if pd.isna(r.Latitud) else r.Latitud,
            None if pd.isna(r.Longitud) else r.Longitud,
            None if pd.isna(r.Codi_Barri) else int(r.Codi_Barri),
            None if pd.isna(r.Codi_Districte) else int(r.Codi_Districte),
        )
        for r in df.itertuples()
    ]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE commercial_premises")
        execute_values(
            cur,
            """
            INSERT INTO commercial_premises
                (id, activity_status, sector, activity_group, activity_name, name, address, lat, lon, neighborhood_code, district_code)
            VALUES %s
            """,
            rows,
        )
    conn.commit()
    print(f"commercial_premises: {len(rows)} rows")


def load_population(conn, df: pd.DataFrame) -> None:
    df = df.copy()
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)
    agg = df.groupby(["Data_Referencia", "Codi_Barri", "EDAT_1", "SEXE"], as_index=False)["Valor"].sum()

    rows = [
        (r.Data_Referencia, int(r.Codi_Barri), int(r.EDAT_1), int(r.SEXE), int(r.Valor))
        for r in agg.itertuples()
    ]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE population_by_neighborhood")
        execute_values(
            cur,
            "INSERT INTO population_by_neighborhood (reference_date, neighborhood_code, age, sex, people) VALUES %s",
            rows,
        )
    conn.commit()
    print(f"population_by_neighborhood: {len(rows)} rows")


def load_income(conn, df: pd.DataFrame) -> None:
    df = df.copy()
    df["Import_Euros"] = pd.to_numeric(df["Import_Euros"], errors="coerce")
    agg = df.groupby(["Any", "Codi_Barri"], as_index=False)["Import_Euros"].mean()

    rows = [(int(r.Any), int(r.Codi_Barri), round(r.Import_Euros, 2)) for r in agg.itertuples()]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE income_by_neighborhood")
        execute_values(
            cur,
            "INSERT INTO income_by_neighborhood (year, neighborhood_code, income_eur_per_capita) VALUES %s",
            rows,
        )
    conn.commit()
    print(f"income_by_neighborhood: {len(rows)} rows")


def main() -> None:
    comercial = pd.read_csv(SRC_DIR / "comercial.csv", dtype=str, encoding="utf-8-sig")
    poblacio = pd.read_csv(SRC_DIR / "poblacio.csv", dtype=str)
    renda = pd.read_csv(SRC_DIR / "renda.csv", dtype=str)

    conn = psycopg2.connect(DATABASE_URL)
    load_neighborhoods(conn, comercial, poblacio)
    load_commercial_premises(conn, comercial)
    load_population(conn, poblacio)
    load_income(conn, renda)
    conn.close()


if __name__ == "__main__":
    main()
