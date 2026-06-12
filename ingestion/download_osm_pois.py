#!/usr/bin/env python3
"""Download OpenStreetMap points of interest (cafes, bars, restaurants, fast
food, pubs) within Barcelona via the Overpass API, for competitor / amenity
density analysis.

Usage:
    python download_osm_pois.py
"""

import json

import requests

from common import DATA_RAW_DIR

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "GeoYieldAI/1.0 (Barcelona location intelligence)"

CATEGORIES = ["cafe", "bar", "restaurant", "fast_food", "pub"]

QUERY = f"""
[out:json][timeout:180];
area["name"="Barcelona"]["admin_level"="8"]["boundary"="administrative"]->.bcn;
(
  node["amenity"~"^({'|'.join(CATEGORIES)})$"](area.bcn);
  way["amenity"~"^({'|'.join(CATEGORIES)})$"](area.bcn);
);
out center tags;
"""

DEST = DATA_RAW_DIR / "osm" / "barcelona_pois.json"


def main() -> None:
    if DEST.exists():
        print(f"skip (exists): {DEST}")
        return

    print("querying Overpass API for Barcelona POIs...")
    resp = requests.post(
        OVERPASS_URL, data={"data": QUERY}, headers={"User-Agent": USER_AGENT}, timeout=200
    )
    resp.raise_for_status()
    data = resp.json()

    DEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEST.with_suffix(DEST.suffix + ".part")
    with open(tmp, "w") as f:
        json.dump(data, f)
    tmp.rename(DEST)
    print(f"saved {len(data.get('elements', []))} POIs -> {DEST}")


if __name__ == "__main__":
    main()
