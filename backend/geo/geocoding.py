"""
Geocodificación de direcciones de Barcelona: convierte una dirección de
texto libre en coordenadas y, cuando es posible, en el distrito oficial
correspondiente -- usando Nominatim (OpenStreetMap), el mismo proveedor
que ya usamos para las teselas del mapa.

No resuelve la zona PGM (para eso hace falta el servicio Identify del
AMB, con sus propias coordenadas) -- solo el distrito, a partir del
campo 'suburb' que devuelve Nominatim, que en pruebas reales coincide
con los 10 distritos oficiales de Barcelona.

Funciones principales:
- geocodificar_direccion: llama a Nominatim y devuelve coordenadas + distrito sugerido (o None si no se pudo resolver ninguno).
- resolver_distrito_desde_suburb: la lógica de emparejamiento en sí, separada para poder probarla sin red.
"""

import re

import requests

from backend.observability import get_logger

logger = get_logger("geo.geocoding")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Nominatim exige un User-Agent identificable en su política de uso --
# sin esto, puede bloquear o limitar las peticiones.
USER_AGENT = "GeoYieldAI/1.0 (proyecto academico Pontia)"

# Caja delimitadora aproximada de Barcelona ciudad (izquierda, arriba,
# derecha, abajo), para sesgar los resultados hacia aquí y no confundir
# una calle homónima de otra ciudad.
BARCELONA_VIEWBOX = "2.052,41.469,2.228,41.320"

# Los 10 distritos oficiales, en minúsculas, para comparar sin
# sensibilidad a mayúsculas. "les corts" se deja tal cual -- ahí "Les"
# es parte real del nombre, no un artículo que sobra.
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

_ARTICULO_INICIAL_RE = re.compile(r"^(l'|la |el |les )")


def resolver_distrito_desde_suburb(suburb: str | None) -> int | None:
    """
    Empareja el campo 'suburb' de Nominatim con uno de los 10 distritos
    oficiales de Barcelona.

    Primero intenta una coincidencia exacta (cubre "Les Corts", donde el
    artículo es parte real del nombre) y solo si falla, prueba quitando
    un artículo catalán inicial (cubre "l'Eixample" -> "Eixample").
    Devuelve None si no hay coincidencia -- no adivina ni aproxima.
    """
    if not suburb:
        return None

    normalizado = suburb.strip().lower()
    if normalizado in DISTRITOS_BARCELONA:
        return DISTRITOS_BARCELONA[normalizado]

    sin_articulo = _ARTICULO_INICIAL_RE.sub("", normalizado)
    return DISTRITOS_BARCELONA.get(sin_articulo)


def geocodificar_direccion(direccion: str) -> dict | None:
    """
    Busca una dirección dentro de Barcelona vía Nominatim.

    Devuelve None si no se encontró ningún resultado. Si se encontró,
    devuelve un diccionario con lat, lon, direccion_encontrada (el
    display_name completo de Nominatim, para que el usuario confirme
    que es la dirección correcta) y codi_districte (int, o None si no
    se pudo determinar el distrito a partir del resultado).
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
    suburb = address.get("city_district") or address.get("suburb") or address.get("borough")

    return {
        "lat": float(resultado["lat"]),
        "lon": float(resultado["lon"]),
        "direccion_encontrada": resultado.get("display_name", ""),
        "codi_districte": resolver_distrito_desde_suburb(suburb),
    }