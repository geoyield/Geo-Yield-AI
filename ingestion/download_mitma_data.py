#!/usr/bin/env python3
"""Download MITMA mobility data (viajes + personas, por-distritos) for the
most recent N full months, filter to rows touching one of Barcelona's 10
districts, and save the filtered files into data_raw/, mirroring the source
bucket's path layout.

Usage:
    python download_mitma_data.py [--months 6] [--datasets viajes personas]

Files are downloaded to a temporary location, filtered, then written to
data_raw/ and the temporary download is removed. Already-filtered files in
data_raw/ are skipped, so reruns only download new/missing files.
"""

import argparse
import tempfile
from pathlib import Path

import requests

from common import (
    BASE_URL,
    DATA_RAW_DIR,
    DATASETS,
    ZONIFICACION_KEY,
    filter_to_barcelona,
    list_keys,
    recent_full_months,
)


def download_to(key: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading: {key}")
    with requests.get(f"{BASE_URL}/{key}", stream=True, timeout=120) as resp:
        resp.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        tmp.rename(dest)


def download_and_filter(key: str, filter_cols: list[str]) -> None:
    dest = DATA_RAW_DIR / key
    if dest.exists():
        print(f"skip (exists): {key}")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = Path(tmpdir) / Path(key).name
        download_to(key, raw_path)
        kept = filter_to_barcelona(raw_path, dest, filter_cols)
        print(f"filtered: {key} -> {kept} Barcelona-related rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--months",
        type=int,
        default=1,
        help="Number of most recent full months to download per dataset (default: 1)",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=list(DATASETS),
        default=list(DATASETS),
        help="Which datasets to download (default: all)",
    )
    args = parser.parse_args()

    # Zone id -> name lookup, needed to seed the `zones` table. Small file,
    # kept as-is (not filtered).
    zonificacion_dest = DATA_RAW_DIR / ZONIFICACION_KEY
    if not zonificacion_dest.exists():
        download_to(ZONIFICACION_KEY, zonificacion_dest)
    else:
        print(f"skip (exists): {ZONIFICACION_KEY}")

    for dataset in args.datasets:
        prefix = DATASETS[dataset]["prefix"]
        filter_cols = DATASETS[dataset]["filter_cols"]
        months = recent_full_months(prefix, args.months)
        print(f"{dataset}: most recent full months = {months}")
        for month in months:
            for key in list_keys(f"{prefix}/{month}/"):
                download_and_filter(key, filter_cols)


if __name__ == "__main__":
    main()
