"""
==============================================================================
API PROTOTYPING: GEOCODING EXPLORATION (SPIKE)
==============================================================================
File: scripts/investigacion_pgm/test_geocoding.py

Geocoding test using Nominatim (OpenStreetMap) — the same provider used for 
the frontend map tiles.

Before building the final FastAPI endpoint, this script acts as a 'Spike' to 
verify two critical uncertainties:
1. Does Nominatim return accurate coordinates for real Barcelona addresses 
   when constrained by a geographic bounding box (viewbox)?
2. Does its response payload include metadata that can be mapped to a DISTRICT? 
   (We don't have district polygons loaded yet). This is unconfirmed for 
   Barcelona specifically.
"""

import json

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# API Compliance: Nominatim's Fair Use Policy requires an identifiable User-Agent.
# Without it, requests are silently throttled or blocked (HTTP 403).
USER_AGENT = "GeoYieldAI/1.0 (proyecto academico Pontia)"

# Geospatial Bounding Box for Barcelona (min_lon, max_lat, max_lon, min_lat).
# Forces the search algorithm to heavily bias results within the city limits.
BARCELONA_VIEWBOX = "2.052,41.469,2.228,41.320"

DIRECCIONES_DE_PRUEBA = [
    "Carrer de Sant Pau 1, Barcelona",
    "Rambla del Poblenou 100, Barcelona",
    "Passeig de Gràcia 50, Barcelona",
]


def probar():
    for direccion in DIRECCIONES_DE_PRUEBA:
        print("=" * 70)
        print(f"Buscando: {direccion}")
        print("=" * 70)

        # Query parameters configured for strict JSON response and bounded search
        params = {
            "q": direccion,
            "format": "jsonv2",
            "limit": 1,
            "viewbox": BARCELONA_VIEWBOX,
            "bounded": 1,
            "addressdetails": 1, # Crucial: requests the breakdown of the address (city, suburb, etc.)
        }
        response = requests.get(NOMINATIM_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=5)
        print(f"HTTP: {response.status_code}")

        resultados = response.json()
        if not resultados:
            print("Sin resultados.\n")
            continue

        # Dumps the raw JSON response to inspect the exact schema returned by the API
        print(json.dumps(resultados[0], ensure_ascii=False, indent=2))
        print()


if __name__ == "__main__":
    probar()