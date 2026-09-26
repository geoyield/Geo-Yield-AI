"""
==============================================================================
DATA WRANGLING: API PROBE (SCHEMA DISCOVERY)
==============================================================================
File: scripts/investigacion_pgm/amb_diagnosis.py

Initial exploratory script (Phase 4) used to blindly interrogate the AMB 
Open Data API. It retrieves the raw payload without making any assumptions 
about the JSON schema or data structure.

Architectural Note:
This is a standalone diagnostic script. It intentionally does not import 
models from the `backend/` application to avoid tightly coupling early 
exploration to strict database schemas.
"""

import json
import requests

URL = "https://opendata.amb.cat/api-amb/search/articles_NUMAMB?from=0&size=999&entity=article&pla=num_pgm"


def diagnosticar():
    # Schema Discovery: Do not assume the shape of the data based on docs.
    print("Descargando (sin asumir nada sobre la forma de la respuesta todavía)...")
    response = requests.get(URL)
    print(f"Código HTTP: {response.status_code}")
    if response.status_code != 200:
        print("La petición falló -- revisa la URL antes de seguir.")
        return

    data = response.json()

    print(f"\nTipo de 'data': {type(data)}")
    if isinstance(data, dict):
        print(f"Claves de nivel superior: {list(data.keys())}")
    elif isinstance(data, list):
        print(f"Es una lista con {len(data)} elementos")

    # ------------------------------------------------------------------------------
    # API RATE LIMIT PROTECTION (LOCAL CACHING)
    # ------------------------------------------------------------------------------
    # Save the raw unparsed payload to disk.
    # Why? It allows subsequent Data Wrangling scripts to iterate over the 500+ 
    # articles thousands of times during development without hammering the 
    # government server, avoiding API Rate Limits or IP bans.
    with open('raw_response.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\nRespuesta completa guardada en respuesta_cruda.json -- ábrelo y mira un artículo entero")
    print("antes de que filtremos nada, para confirmar los nombres reales de los campos.")


if __name__ == "__main__":
    diagnosticar()