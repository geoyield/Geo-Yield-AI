"""
Continuación de extraer_candidatos.py:

1. Trae el Artículo 304 (referencia cruzada citada dentro del 306).
2. Busca en TODOS los artículos (no solo los del Títol IV) cualquier
   título que mencione "desenvolupament" -- las claus 19, 20b y 22b no
   aparecieron en el Títol IV, pero podrían regularse en otra sección
   del PGM dedicada específicamente a zonas de desarrollo pendiente.

No asigna zona_pgm ni carga nada a la base de datos: solo busca y
muestra, para decidir después de leer el contenido real.
"""

import json
import re


def limpiar_html(texto: str) -> str:
    if not texto:
        return ""
    texto = re.sub(r"<br\s*/?>", "\n", texto)
    texto = re.sub(r"</li>", "\n", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = texto.replace("&nbsp;", " ").replace("&amp;", "&")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def main():
    with open("respuesta_cruda.json", encoding="utf-8") as f:
        data = json.load(f)

    items = data["items"]

    # 1. Artículo 304 (referencia cruzada del 306)
    print("=" * 70)
    print("ARTÍCULO 304 (referencia cruzada citada en el 306)")
    print("=" * 70)
    encontrado_304 = False
    for item in items:
        if item.get("numeroArticle") == "304":
            encontrado_304 = True
            print(f"Título real: {item.get('titol', {}).get('ca_ES', '')}")
            print()
            print(limpiar_html(item.get("description", {}).get("ca_ES", "")))
    if not encontrado_304:
        print("No se encontró el Artículo 304 en la respuesta.")

    # 2. Búsqueda ampliada de "desenvolupament" en TODOS los 574 artículos,
    #    no solo los del Títol IV -- para 19, 20b, 22b.
    print()
    print("=" * 70)
    print("BÚSQUEDA AMPLIADA: 'desenvolupament' en TODOS los artículos")
    print("=" * 70)
    candidatos = []
    for item in items:
        titulo = item.get("titol", {}).get("ca_ES", "")
        if "desenvolupament" in titulo.lower():
            seccion = item.get("titolNormativa", [{}])[0].get("label", {}).get("ca_ES", "?")
            candidatos.append((item.get("numeroArticle"), titulo, seccion))

    if not candidatos:
        print("Ningún artículo, en todo el PGM, menciona 'desenvolupament' en su título.")
    else:
        for numero, titulo, seccion in candidatos:
            print(f"Art. {numero} -- {titulo}  [sección: {seccion}]")


if __name__ == "__main__":
    main()