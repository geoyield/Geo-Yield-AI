"""Shared constants and helpers for MITMA ingestion scripts."""

import os
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import requests

BASE_URL = "https://movilidad-opendata.mitma.es"
S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

# Barcelona's 10 administrative districts (MITMA "distritos" zonification:
# municipality code 08019 + district number 01-10).
BARCELONA_DISTRICT_IDS = {f"08019{i:02d}" for i in range(1, 11)}

ZONIFICACION_KEY = "zonificacion/zonificacion_distritos/nombres_distritos.csv"

# Columns checked against BARCELONA_DISTRICT_IDS to decide whether a row is
# kept. A row is kept if *any* of these columns is a Barcelona district.
DATASETS = {
    "viajes": {
        "prefix": "estudios_basicos/por-distritos/viajes/ficheros-diarios",
        "filter_cols": ["origen", "destino"],
    },
    "personas": {
        "prefix": "estudios_basicos/por-distritos/personas/ficheros-diarios",
        "filter_cols": ["zona_pernoctacion"],
    },
}

FILTER_CHUNK_SIZE = 500_000

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = Path(os.environ.get("DATA_RAW_DIR", REPO_ROOT / "data_raw"))


def list_common_prefixes(prefix: str) -> list[str]:
    """List S3 'directories' (CommonPrefixes) directly under `prefix`."""
    resp = requests.get(
        f"{BASE_URL}/",
        params={"list-type": "2", "prefix": prefix, "delimiter": "/"},
        timeout=30,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    return [
        el.find(f"{S3_NS}Prefix").text
        for el in root.findall(f"{S3_NS}CommonPrefixes")
    ]


def list_keys(prefix: str) -> list[str]:
    """List object keys directly under `prefix`."""
    resp = requests.get(
        f"{BASE_URL}/",
        params={"list-type": "2", "prefix": prefix},
        timeout=30,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    return [el.find(f"{S3_NS}Key").text for el in root.findall(f"{S3_NS}Contents")]


def filter_to_barcelona(src_path: Path, dest_path: Path, filter_cols: list[str]) -> int:
    """Stream `src_path` (pipe-delimited, gzip), keep only rows where any of
    `filter_cols` is a Barcelona district, and write the result to
    `dest_path` (gzip, same columns/header). Returns the number of rows kept.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest_path.with_suffix(dest_path.suffix + ".part")

    total = 0
    first = True
    for chunk in pd.read_csv(src_path, sep="|", compression="gzip", dtype=str, chunksize=FILTER_CHUNK_SIZE):
        mask = False
        for col in filter_cols:
            mask = mask | chunk[col].isin(BARCELONA_DISTRICT_IDS)
        filtered = chunk[mask]
        total += len(filtered)
        filtered.to_csv(
            tmp,
            sep="|",
            index=False,
            mode="w" if first else "a",
            header=first,
            compression="gzip",
        )
        first = False

    if first:
        # Source had no rows at all; still produce an (empty, header-only) file.
        pd.read_csv(src_path, sep="|", dtype=str, nrows=0).to_csv(tmp, sep="|", index=False, compression="gzip")

    tmp.rename(dest_path)
    return total


def recent_full_months(dataset_prefix: str, months: int, min_days: int = 28) -> list[str]:
    """Return the most recent `months` year-month strings (YYYY-MM) under
    `dataset_prefix` that have at least `min_days` daily files, i.e. "full"
    months as opposed to months with only a handful of sample days.
    """
    all_months = sorted(
        p.rstrip("/").rsplit("/", 1)[-1] for p in list_common_prefixes(f"{dataset_prefix}/")
    )
    full_months = [
        month for month in all_months if len(list_keys(f"{dataset_prefix}/{month}/")) >= min_days
    ]
    return full_months[-months:]
