"""
Wrapper del servicio Identify del AMB (geoportal.amb.cat) para resolver
la zona PGM real dado un punto, usado junto con geocoding.py para pasar
de una dirección de texto a una zona PGM sugerida.

Solo se aceptan los códigos CLAU_URB para los que ya tenemos normativa
legal verificada y cargada (ver CLAU_URB_A_ZONA_PGM) -- cualquier otro
código que devuelva el servicio (red viaria, zonas verdes, sistemas,
zonas de "desenvolupament" sin artículo propio...) se descarta
automáticamente al no aparecer en la tabla, en vez de mantener aparte
una lista de "qué excluir".
"""

import time

import requests

from backend.observability import get_logger

logger = get_logger("geo.amb_identify")

AMB_IDENTIFY_URL = "https://geoportal.amb.cat/geoserveis/rest/services/pla_general_metropolita_1976/MapServer/identify"

# El servicio público del AMB puede tardar más de lo esperado en
# ocasiones (confirmado con un timeout real durante las pruebas) --
# mismo criterio de reintento ya aplicado para los 503 transitorios de
# Gemini en gemini_adapter.py.
MAX_REINTENTOS = 2
ESPERA_ENTRE_REINTENTOS_SEGUNDOS = 1
TIMEOUT_SEGUNDOS = 8

# Traducción CLAU_URB (código del AMB) -> zona_pgm (nuestro identificador
# interno). Construida y verificada artículo por artículo -- ver el
# historial de la sesión de investigación para la evidencia de cada uno.
#
# Confirmados contra respuestas reales del servicio: "12", "12b", "13a".
# El resto (13b, 15, 18, 17, 6, 20a, 22a) vienen de la leyenda publicada
# del AMB, pendientes de confirmar su representación exacta.
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
    Recorre los resultados del Identify y devuelve el primer código
    CLAU_URB que tengamos traducido. Separado de identificar_zona_pgm
    para poder probar el filtrado sin necesidad de red.
    """
    for resultado in resultados:
        clau_urb = str(resultado.get("attributes", {}).get("CLAU_URB", "")).strip()
        zona_pgm = CLAU_URB_A_ZONA_PGM.get(clau_urb)
        if zona_pgm is not None:
            return {"zona_pgm": zona_pgm, "clau_urb": clau_urb}
    return None


def identificar_zona_pgm(lat: float, lon: float) -> dict | None:
    """
    Consulta el servicio Identify del AMB para el punto dado, con
    reintento automático si el servicio tarda más de lo esperado.

    Devuelve {"zona_pgm": ..., "clau_urb": ...} si alguno de los
    resultados corresponde a un código con normativa cargada, o None si
    no hay ningún resultado, ninguno tiene normativa cargada, o el
    servicio no responde tras los reintentos -- nunca inventa una zona.
    """
    params = {
        "geometry": f'{{"x":{lon},"y":{lat}}}',
        "geometryType": "esriGeometryPoint",
        "sr": 4326,
        "layers": "all",
        "tolerance": 2,
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