"""Live lookups against the Sede Electronica del Catastro's free OVC web
services (no API key required): coordinates -> cadastral reference ->
building details (use, total surface, construction year, unit breakdown).
"""

import xml.etree.ElementTree as ET

import requests

OVC_BASE = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC"
NS = "{http://www.catastro.meh.es/}"


class CatastroError(Exception):
    pass


def _request(url: str, params: dict) -> ET.Element:
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    err = root.find(f".//{NS}lerr/{NS}err/{NS}des")
    if err is not None:
        raise CatastroError(err.text)

    return root


def _to_number(value: str | None):
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return float(value.replace(",", "."))


def coords_to_reference(lat: float, lon: float) -> dict:
    root = _request(
        f"{OVC_BASE}/OVCCoordenadas.asmx/Consulta_RCCOOR",
        {"SRS": "EPSG:4326", "Coordenada_X": lon, "Coordenada_Y": lat},
    )
    coord = root.find(f".//{NS}coord")
    pc1 = coord.findtext(f"{NS}pc/{NS}pc1")
    pc2 = coord.findtext(f"{NS}pc/{NS}pc2")
    return {"cadastral_reference": pc1 + pc2, "address": coord.findtext(f"{NS}ldt")}


def reference_to_parcel(rc: str) -> dict:
    root = _request(
        f"{OVC_BASE}/OVCCallejero.asmx/Consulta_DNPRC",
        {"Provincia": "BARCELONA", "Municipio": "BARCELONA", "RC": rc},
    )
    bi = root.find(f".//{NS}bi")
    debi = bi.find(f"{NS}debi")

    units = []
    for cons in root.findall(f".//{NS}lcons/{NS}cons"):
        loint = cons.find(f"{NS}dt/{NS}lourb/{NS}loint")
        units.append(
            {
                "use": cons.findtext(f"{NS}lcd"),
                "floor": loint.findtext(f"{NS}pt") if loint is not None else None,
                "door": loint.findtext(f"{NS}pu") if loint is not None else None,
                "surface_m2": _to_number(cons.findtext(f"{NS}dfcons/{NS}stl")),
            }
        )

    return {
        "cadastral_reference": rc,
        "address": bi.findtext(f"{NS}ldt"),
        "use": debi.findtext(f"{NS}luso"),
        "total_surface_m2": _to_number(debi.findtext(f"{NS}sfc")),
        "year_built": _to_number(debi.findtext(f"{NS}ant")),
        "units": units,
    }


def lookup_parcel(lat: float, lon: float) -> dict:
    ref = coords_to_reference(lat, lon)
    return reference_to_parcel(ref["cadastral_reference"])
