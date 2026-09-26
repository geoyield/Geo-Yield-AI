"""
==============================================================================
GEOCODING ENGINE (OPENSTREETMAP NOMINATIM)
==============================================================================
File: backend/geo/geocoding.py

Translates a free-text address into spatial coordinates (Lat/Lon) and, when 
possible, extracts the official Barcelona District code. 

Architectural Note (Separation of Concerns):
This module DOES NOT resolve the PGM Urban Zoning. Urban zoning requires the 
official AMB Identify service (`amb_identify.py`) using the coordinates generated 
here. This file relies exclusively on the 'suburb' field returned by Nominatim, 
which empirical testing confirmed matches Barcelona's 10 official districts.
"""

import re

import requests

from backend.observability import get_logger

logger = get_logger("geo.geocoding")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# API Compliance: User-Agent is mandatory to prevent 403 Forbidden errors.
USER_AGENT = "GeoYieldAI/1.0 (proyecto academico Pontia)"

# Geospatial Bounding Box (min_lon, max_lat, max_lon, min_lat).
# Restricts results to the Barcelona metropolitan area to prevent false positives 
# (e.g., resolving a street name to another city).
BARCELONA_VIEWBOX = "2.052,41.469,2.228,41.320"

# Official 10 districts mapped to their integer codes.
# Stored in lowercase for case-insensitive matching. Note that "les corts" 
# retains the article "les" as it is officially part of the proper noun.
DISTRITOS_BARCELONA = {
    "ciutat vella": 1,
    "eixample": 2,
    "sants-montjuïc": 3,
    "les corts": 4,
    "sarrià-sant gervasi": 5,
    "gràcia": 6,
    "horta-guinardó": 7,
    "nou barris": 8,
    "sant andreu": 9,
    "sant martí": 10,
}

# Regex to detect and strip Catalan grammatical articles at the start of a string.
_ARTICULO_INICIAL_RE = re.compile(r"^(l'|la |el |les )")


def resolver_distrito_desde_suburb(suburb: str | None) -> int | None:
    """
    Maps Nominatim's 'suburb' field to one of the 10 official Barcelona districts.

    Lexical Strategy:
    1. Attempts an EXACT match first (crucial for "Les Corts").
    2. If it fails, strips the leading Catalan article using Regex and retries 
       (e.g., "l'Eixample" -> "Eixample").
    3. Returns None if no match is found (Fail-Safe: no fuzzy guessing).
    """
    if not suburb:
        return None

    normalizado = suburb.strip().lower()

    # Attempt 1: Exact Match
    if normalizado in DISTRITOS_BARCELONA:
        return DISTRITOS_BARCELONA[normalizado]

    # Attempt 2: Strip article and retry
    sin_articulo = _ARTICULO_INICIAL_RE.sub("", normalizado)
    return DISTRITOS_BARCELONA.get(sin_articulo)


def geocodificar_direccion(direccion: str) -> dict | None:
    """
    Queries Nominatim for a free-text address within the Barcelona bounding box.

    Returns a dictionary containing:
    - lat, lon: Spatial coordinates (float).
    - direccion_encontrada: The full 'display_name' for UX validation.
    - codi_districte: The resolved integer district code (or None if unresolvable).
    
    Returns None if the network request fails or yields no results.
    """
    params = {
        "q": direccion,
        "format": "jsonv2",
        "limit": 1,
        "viewbox": BARCELONA_VIEWBOX,
        "bounded": 1,
        "addressdetails": 1,
    }
    try:
        response = requests.get(NOMINATIM_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=5)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception(f"Error consultando Nominatim para la dirección: {direccion!r}")
        return None

    resultados = response.json()
    if not resultados:
        return None

    resultado = resultados[0]
    address = resultado.get("address", {})

    # Fallback cascade to extract the most relevant localized neighborhood data
    suburb = address.get("city_district") or address.get("suburb") or address.get("borough")

    return {
        "lat": float(resultado["lat"]),
        "lon": float(resultado["lon"]),
        "direccion_encontrada": resultado.get("display_name", ""),
        "codi_districte": resolver_distrito_desde_suburb(suburb),
    }