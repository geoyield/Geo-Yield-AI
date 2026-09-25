"""
==============================================================================
GIS INTEGRATION: AMB IDENTIFY SERVICE (URBAN ZONING)
==============================================================================
File: backend/geo/amb_identify.py

Wrapper for the official AMB (Área Metropolitana de Barcelona) Identify service.
Performs Point-in-Polygon intersection to translate spatial coordinates (Lat/Lon) 
into the official PGM Urban Zoning code (CLAU_URB).

Security by Design (Allow-listing):
Only CLAU_URB codes that have verified legal text ingested in the RAG database 
are accepted. Any other code (roads, parks, undeveloped land) is automatically 
discarded.
"""

import logging
import time

import requests

logger = logging.getLogger("geoyield_geocoding")

# Note: Using the live MapServer instead of the cached _25831 to ensure 
# we query the most up-to-date legal geometries.
AMB_IDENTIFY_URL = "https://geoportal.amb.cat/geoserveis/rest/services/pla_general_metropolita_1976/MapServer/identify"

# Network Resilience Config: 
# Public government APIs can be slow or unstable. Implementing a retry policy 
# to survive transient network failures without crashing the user request.
MAX_REINTENTOS = 2
ESPERA_ENTRE_REINTENTOS_SEGUNDOS = 1
TIMEOUT_SEGUNDOS = 8

# Allow-list mapping: AMB Code (CLAU_URB) -> Internal RAG Identifier (zona_pgm)
CLAU_URB_A_ZONA_PGM = {
    "12": "nucli_antic",
    "12b": "nucli_antic",
    "13a": "densificacio_urbana",
    "13b": "densificacio_urbana",
    "15": "conservacio_estructura_urbana",
    "18": "ordenacio_volumetrica_especifica",
    "17": "renovacio_urbana",
    "6": "renovacio_urbana",
    "20a": "edificacio_aillada",
    "22a": "industrial",
}


def _extraer_zona_de_resultados(resultados: list[dict]) -> dict | None:
    """
    Iterates through the Point-in-Polygon results and returns the first 
    CLAU_URB code that exists in our Allow-list. 
    Separated from the network call to allow isolated Unit Testing without HTTP.
    """
    for resultado in resultados:
        clau_urb = str(resultado.get("attributes", {}).get("CLAU_URB", "")).strip()
        zona_pgm = CLAU_URB_A_ZONA_PGM.get(clau_urb)
        if zona_pgm is not None:
            return {"zona_pgm": zona_pgm, "clau_urb": clau_urb}
    return None


def identificar_zona_pgm(lat: float, lon: float) -> dict | None:
    """
    Queries the AMB Identify service for a given spatial point.
    Implements automatic retries on timeout.

    Returns {"zona_pgm": ..., "clau_urb": ...} if a valid, supported zone is found.
    Returns None if the network fails, or if the zone is unsupported.
    """
    params = {
        "geometry": f'{{"x":{lon},"y":{lat}}}',
        "geometryType": "esriGeometryPoint",
        "sr": 4326, # WGS84 Spatial Reference
        "layers": "all",
        "tolerance": 2, # Pixel tolerance for the intersection
        "mapExtent": f"{lon - 0.01},{lat - 0.01},{lon + 0.01},{lat + 0.01}",
        "imageDisplay": "400,400,96",
        "returnGeometry": "false",
        "f": "json",
    }

    for intento in range(MAX_REINTENTOS + 1):
        try:
            response = requests.get(AMB_IDENTIFY_URL, params=params, timeout=TIMEOUT_SEGUNDOS)
            response.raise_for_status()
            data = response.json()
            return _extraer_zona_de_resultados(data.get("results", []))
        except requests.RequestException:
            if intento < MAX_REINTENTOS:
                logger.warning(
                    f"Timeout o error consultando el servicio Identify del AMB para ({lat}, {lon}), "
                    f"reintentando en {ESPERA_ENTRE_REINTENTOS_SEGUNDOS}s... (intento {intento + 1}/{MAX_REINTENTOS})"
                )
                time.sleep(ESPERA_ENTRE_REINTENTOS_SEGUNDOS)
            else:
                logger.exception(
                    f"El servicio Identify del AMB no respondió tras {MAX_REINTENTOS + 1} intentos para ({lat}, {lon})"
                )
                return None