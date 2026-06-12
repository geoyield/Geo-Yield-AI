#!/usr/bin/env python3
"""Download Open Data BCN datasets (Barcelona's 73 neighborhoods, much finer
than MITMA's 10 districts) into data_raw/opendata_bcn/.

These datasets are already scoped to Barcelona, so no filtering is needed:
  - cens d'activitats comercials (ground-floor commercial premises)
  - padró: population by neighborhood/age/sex
  - RFD: disposable household income per capita by census section

Usage:
    python download_opendata_bcn.py
"""

from pathlib import Path

import requests

from common import DATA_RAW_DIR

OPENDATA_BCN_BASE = "https://opendata-ajuntament.barcelona.cat/data/dataset"

FILES = {
    # Cens de locals en planta baixa destinats a activitat economica (2024).
    "comercial.csv": (
        f"{OPENDATA_BCN_BASE}/fe177673-0f83-42e7-b35a-ddea901be8bc/resource/"
        "38babeec-5c47-43d3-84e7-b13a4b89004f/download/"
        "241021_censcomercialbcn_opendata_2024_v5.csv"
    ),
    # Poblacio per sexe i edat (latest year).
    "poblacio.csv": (
        f"{OPENDATA_BCN_BASE}/d978cd89-53f7-41be-b4ba-91a0b5d36f71/resource/"
        "2cb440e7-0cd3-4cfe-9645-ca09a18bccf9/download"
    ),
    # Renda disponible de les llars per capita (2022).
    "renda.csv": (
        f"{OPENDATA_BCN_BASE}/78db0c75-fa56-4604-9510-8b92834a7fd2/resource/"
        "3df0c5b9-de69-4c94-b924-57540e52932f/download/"
        "2022_renda_disponible_llars_per_persona.csv"
    ),
}

DEST_DIR = DATA_RAW_DIR / "opendata_bcn"


def download(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"skip (exists): {dest.name}")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading: {dest.name}")
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        tmp.rename(dest)


def main() -> None:
    for filename, url in FILES.items():
        download(url, DEST_DIR / filename)


if __name__ == "__main__":
    main()
