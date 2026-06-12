#!/usr/bin/env python3
"""Load data_raw/ files (already filtered to Barcelona-related rows by
download_mitma_data.py) into Postgres.

Usage:
    python load_mitma_data.py [--force] [--datasets viajes personas]

Idempotent: each processed daily file is recorded in `ingestion_state`, so
reruns skip files that were already loaded (unless --force is given).
"""

import argparse
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from common import BARCELONA_DISTRICT_IDS, DATA_RAW_DIR, DATASETS, ZONIFICACION_KEY

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/geoyield"
)

CHUNK_SIZE = 500_000


def load_zones(conn) -> None:
    path = DATA_RAW_DIR / ZONIFICACION_KEY
    df = pd.read_csv(path, sep="|", header=None, names=["id", "name"], dtype=str)
    rows = [(row.id, row.name, row.id in BARCELONA_DISTRICT_IDS) for row in df.itertuples()]

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO zones (id, name, is_barcelona) VALUES %s
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, is_barcelona = EXCLUDED.is_barcelona
            """,
            rows,
        )
    conn.commit()
    print(f"zones: upserted {len(rows)} rows")


def already_loaded(conn, dataset: str, file_date) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM ingestion_state WHERE dataset = %s AND file_date = %s",
            (dataset, file_date),
        )
        return cur.fetchone() is not None


def mark_loaded(conn, dataset: str, file_date, row_count: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion_state (dataset, file_date, row_count, loaded_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (dataset, file_date)
            DO UPDATE SET row_count = EXCLUDED.row_count, loaded_at = now()
            """,
            (dataset, file_date, row_count),
        )
    conn.commit()


def _aggregate(path: Path, usecols, dtypes, group_cols, sum_cols):
    """Aggregate an already Barcelona-filtered data_raw/ file (see
    download_mitma_data.py) by summing `sum_cols` over `group_cols`.
    """
    parts = []
    for chunk in pd.read_csv(
        path, sep="|", compression="gzip", usecols=usecols, dtype=dtypes, chunksize=CHUNK_SIZE
    ):
        if not chunk.empty:
            parts.append(chunk.groupby(group_cols, as_index=False)[sum_cols].sum())

    if not parts:
        return None

    return pd.concat(parts, ignore_index=True).groupby(group_cols, as_index=False)[sum_cols].sum()


def load_viajes_file(conn, path: Path) -> int:
    cols = ["fecha", "periodo", "origen", "destino", "viajes", "viajes_km"]
    dtypes = {
        "fecha": str,
        "periodo": "int16",
        "origen": str,
        "destino": str,
        "viajes": "float64",
        "viajes_km": "float64",
    }

    agg = _aggregate(
        path,
        usecols=cols,
        dtypes=dtypes,
        group_cols=["fecha", "periodo", "origen", "destino"],
        sum_cols=["viajes", "viajes_km"],
    )
    if agg is None:
        return 0

    rows = [
        (datetime.strptime(r.fecha, "%Y%m%d").date(), int(r.periodo), r.origen, r.destino, r.viajes, r.viajes_km)
        for r in agg.itertuples()
    ]
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO mobility_flows_hourly (date, hour, origin_zone_id, destination_zone_id, trips, trips_km)
            VALUES %s
            ON CONFLICT (date, hour, origin_zone_id, destination_zone_id)
            DO UPDATE SET trips = EXCLUDED.trips, trips_km = EXCLUDED.trips_km
            """,
            rows,
        )
    conn.commit()
    return len(rows)


def load_personas_file(conn, path: Path) -> int:
    cols = ["fecha", "zona_pernoctacion", "personas"]
    dtypes = {"fecha": str, "zona_pernoctacion": str, "personas": "float64"}

    agg = _aggregate(
        path,
        usecols=cols,
        dtypes=dtypes,
        group_cols=["fecha", "zona_pernoctacion"],
        sum_cols=["personas"],
    )
    if agg is None:
        return 0

    rows = [
        (datetime.strptime(r.fecha, "%Y%m%d").date(), r.zona_pernoctacion, r.personas)
        for r in agg.itertuples()
    ]
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO zone_population_daily (date, zone_id, people)
            VALUES %s
            ON CONFLICT (date, zone_id) DO UPDATE SET people = EXCLUDED.people
            """,
            rows,
        )
    conn.commit()
    return len(rows)


LOADERS = {"viajes": load_viajes_file, "personas": load_personas_file}


def file_date_from_name(path: Path):
    # e.g. 20250301_Viajes_distritos.csv.gz -> date(2025, 3, 1)
    return datetime.strptime(path.name[:8], "%Y%m%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="Reload files even if already recorded in ingestion_state"
    )
    parser.add_argument(
        "--datasets", nargs="+", choices=list(DATASETS), default=list(DATASETS)
    )
    args = parser.parse_args()

    conn = psycopg2.connect(DATABASE_URL)
    load_zones(conn)

    for dataset in args.datasets:
        prefix = DATASETS[dataset]["prefix"]
        loader = LOADERS[dataset]
        files = sorted((DATA_RAW_DIR / prefix).rglob("*.csv.gz"))
        print(f"{dataset}: {len(files)} files found in data_raw/")
        for path in files:
            file_date = file_date_from_name(path)
            if not args.force and already_loaded(conn, dataset, file_date):
                continue
            row_count = loader(conn, path)
            mark_loaded(conn, dataset, file_date, row_count)
            print(f"{dataset} {file_date}: {row_count} rows")

    conn.close()


if __name__ == "__main__":
    main()
