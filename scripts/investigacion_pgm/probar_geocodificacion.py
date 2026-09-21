"""
Prueba de geocodificación con Nominatim (OpenStreetMap) -- el mismo
proveedor que ya usamos para las teselas del mapa.

Antes de construir el endpoint definitivo, esto verifica dos cosas que
todavía no sabemos con certeza:
1. Si Nominatim devuelve coordenadas correctas para direcciones reales
   de Barcelona con el sesgo geográfico (viewbox) que le pedimos.
2. Si su respuesta incluye algo que sirva para identificar el DISTRITO
   (no tenemos los polígonos de distrito cargados todavía) -- puede que
   sí, puede que no, no está confirmado para Barcelona en concreto.
"""

import json

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Nominatim exige un User-Agent identificable en su política de uso --
# sin esto, puede bloquear o limitar las peticiones.
USER_AGENT = "GeoYieldAI/1.0 (proyecto academico Pontia)"

# Caja delimitadora aproximada de Barcelona ciudad (izquierda, arriba,
# derecha, abajo), para sesgar los resultados hacia aquí.
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

        params = {
            "q": direccion,
            "format": "jsonv2",
            "limit": 1,
            "viewbox": BARCELONA_VIEWBOX,
            "bounded": 1,
            "addressdetails": 1,
        }
        response = requests.get(NOMINATIM_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=5)
        print(f"HTTP: {response.status_code}")

        resultados = response.json()
        if not resultados:
            print("Sin resultados.\n")
            continue

        print(json.dumps(resultados[0], ensure_ascii=False, indent=2))
        print()


if __name__ == "__main__":
    probar()