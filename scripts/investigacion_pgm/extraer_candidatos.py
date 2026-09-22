"""
Extrae el texto completo de los artículos candidatos identificados en la
investigación (305, 306, 307, 308, 309, 313), usando los nombres de campo
reales confirmados contra la API de la AMB -- no los adivinados del
script original.

No asigna zona_pgm ni guarda nada en la base de datos: solo extrae y
limpia el texto completo de cada candidato, para revisarlo a mano antes
de decidir si se incorpora al corpus. La zona_pgm final para cada uno se
decide después de leer el contenido completo, no antes.
"""

import json
import re

# Candidatos por título, según la investigación -- pendientes de
# verificar su contenido completo antes de aceptarlos.
ARTICULOS_CANDIDATOS = {
    "305": "clau 15 -- Conservació de l'estructura urbana i edificatòria",
    "306": "clau 18 -- Ordenació volumètrica específica",
    "307": "clau 20a (subzones unifamiliars) -- Ordenació en edificació aïllada",
    "308": "clau 20a (subzones plurifamiliars I-IV) -- Ordenació en edificació aïllada",
    "309": "clau 20a (subzona plurifamiliar V) -- Ordenació en edificació aïllada",
    "313": "clau 17/6 -- Renovació urbana",
}


def limpiar_html(texto: str) -> str:
    """Quita etiquetas HTML conservando estructura legible (saltos de línea por <br>/<li>)."""
    if not texto:
        return ""
    texto = re.sub(r"<br\s*/?>", "\n", texto)
    texto = re.sub(r"</li>", "\n", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = texto.replace("&nbsp;", " ").replace("&amp;", "&")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def extraer_candidatos():
    with open("respuesta_cruda.json", encoding="utf-8") as f:
        data = json.load(f)

    encontrados = {}
    for item in data["items"]:
        numero = item.get("numeroArticle")
        if numero in ARTICULOS_CANDIDATOS:
            titulo = item.get("titol", {}).get("ca_ES", "")
            contenido = limpiar_html(item.get("description", {}).get("ca_ES", ""))
            encontrados[numero] = {"titulo": titulo, "contenido": contenido}

    faltantes = set(ARTICULOS_CANDIDATOS) - set(encontrados)
    if faltantes:
        print(f"AVISO: no se encontraron estos artículos en la respuesta: {faltantes}")

    with open("candidatos_para_revisar.json", "w", encoding="utf-8") as f:
        json.dump(encontrados, f, ensure_ascii=False, indent=2)

    print(f"Extraídos {len(encontrados)} de {len(ARTICULOS_CANDIDATOS)} candidatos.")
    print("Guardado también en candidatos_para_revisar.json.\n")

    for numero, info in encontrados.items():
        print("=" * 70)
        print(f"Artículo {numero} -- candidato para {ARTICULOS_CANDIDATOS[numero]}")
        print(f"Título real: {info['titulo']}")
        print("=" * 70)
        print(info["contenido"])
        print()


if __name__ == "__main__":
    extraer_candidatos()