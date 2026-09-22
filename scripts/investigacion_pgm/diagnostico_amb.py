import json
import requests

URL = "https://opendata.amb.cat/api-amb/search/articles_NUMAMB?from=0&size=999&entity=article&pla=num_pgm"


def diagnosticar():
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

    # Guardamos la respuesta CRUDA, sin procesar nada, para poder inspeccionarla con calma
    with open('respuesta_cruda.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\nRespuesta completa guardada en respuesta_cruda.json -- ábrelo y mira un artículo entero")
    print("antes de que filtremos nada, para confirmar los nombres reales de los campos.")


if __name__ == "__main__":
    diagnosticar()