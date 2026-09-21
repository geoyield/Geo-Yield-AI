"""
Normaliza los nombres de fichero en data/raw/legal/ (quita espacios,
acentos y caracteres especiales) sin tocar el contenido.

Por defecto solo MUESTRA los cambios propuestos, no renombra nada.
Para aplicar de verdad: python normalizar_nombres.py --aplicar

Bórralo cuando ya no lo necesites -- no es parte del pipeline permanente.
"""

import argparse
import re
import unicodedata
from pathlib import Path

LEGAL_DIR = Path("data/raw/legal")


def slugify(filename: str) -> str:
    stem, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
    # Quita acentos (NFKD + descarta los caracteres de combinación)
    stem = unicodedata.normalize("NFKD", stem)
    stem = "".join(c for c in stem if not unicodedata.combining(c))
    # Cualquier cosa que no sea letra/número se convierte en guion bajo
    stem = re.sub(r"[^a-zA-Z0-9]+", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("_").lower()
    return f"{stem}.{ext.lower()}" if ext else stem


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="Renombra de verdad (por defecto solo muestra)")
    args = parser.parse_args()

    if not LEGAL_DIR.exists():
        raise SystemExit(f"No existe {LEGAL_DIR}")

    changes = []
    for f in sorted(LEGAL_DIR.iterdir()):
        if not f.is_file():
            continue
        new_name = slugify(f.name)
        if new_name != f.name:
            changes.append((f, LEGAL_DIR / new_name))

    if not changes:
        print("Ningún nombre necesita cambios.")
        return

    for old, new in changes:
        marker = "->" if args.aplicar else "-- (vista previa) ->"
        print(f"{old.name}\n  {marker} {new.name}\n")

    if not args.aplicar:
        print(f"\n{len(changes)} ficheros se renombrarían. Repasa la lista de arriba y, si está bien, corre:")
        print("  python normalizar_nombres.py --aplicar")
        return

    for old, new in changes:
        if new.exists():
            print(f"AVISO: {new.name} ya existe, se omite {old.name} para no sobrescribir.")
            continue
        old.rename(new)

    print(f"\n{len(changes)} ficheros renombrados.")


if __name__ == "__main__":
    main()