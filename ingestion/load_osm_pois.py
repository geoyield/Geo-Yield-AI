#!/usr/bin/env python3
"""Load data_raw/osm/barcelona_pois.json (from download_osm_pois.py) into
Postgres.

Usage:
    python load_osm_pois.py

Full snapshot: every run truncates and reloads `osm_pois`.
"""

import json
import os

import psycopg2
from psycopg2.extras import execute_values

from common import DATA_RAW_DIR

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/geoyield"
)

SRC = DATA_RAW_DIR / "osm" / "barcelona_pois.json"


def main() -> None:
    with open(SRC) as f:
        data = json.load(f)

    rows = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        amenity = tags.get("amenity")
        if not amenity:
            continue

        if el["type"] == "way":
            center = el.get("center", {})
            lat, lon = center.get("lat"), center.get("lon")
        else:
            lat, lon = el.get("lat"), el.get("lon")

        if lat is None or lon is None:
            continue

        rows.append((el["type"], el["id"], amenity, tags.get("name"), tags.get("cuisine"), lat, lon))

    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE osm_pois")
        execute_values(
            cur,
            "INSERT INTO osm_pois (osm_type, osm_id, category, name, cuisine, lat, lon) VALUES %s",
            rows,
        )
    conn.commit()
    conn.close()
    print(f"osm_pois: {len(rows)} rows")


if __name__ == "__main__":
    main()
