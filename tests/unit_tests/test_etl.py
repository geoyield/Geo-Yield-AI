"""
Tests del ETL.

Se construyen DataFrames sintéticos en memoria (no se leen ficheros) para
que los tests sean rápidos, deterministas y no dependan de datos reales que
no viajan en el repositorio (ver .gitignore).
"""

import pandas as pd
import pytest

from backend.etl.competitors import build_competitors, build_districts, build_neighborhoods, read_raw_census
from backend.etl.income import _extract_district_number, _parse_spanish_number, build_district_income
from backend.etl.mobility import build_district_mobility, read_raw_mobility


class TestParseSpanishNumber:
    def test_thousands_separator_with_trailing_zero(self):
        # Caso que causó el bug real: pandas interpreta "13.990" como float
        # y pierde el cero final si no se lee como texto. Esta función debe
        # recuperar el valor correcto cuando SÍ recibe el texto crudo.
        assert _parse_spanish_number("13.990") == 13990.0

    def test_thousands_separator_no_trailing_zero(self):
        assert _parse_spanish_number("21.976") == 21976.0

    def test_nan_passthrough(self):
        assert pd.isna(_parse_spanish_number(float("nan")))


class TestExtractDistrictNumber:
    def test_extracts_number(self):
        assert _extract_district_number("0801901 Barcelona distrito 01") == 1
        assert _extract_district_number("0801910 Barcelona distrito 10") == 10

    def test_returns_none_when_missing(self):
        assert _extract_district_number(float("nan")) is None


class TestBuildDistrictIncome:
    def _raw_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Municipios": [
                    "08019 Barcelona",  # total municipio, debe descartarse
                    "08019 Barcelona",  # distrito 1, año 2023 (el que debe quedar)
                    "08019 Barcelona",  # distrito 1, sección censal, debe descartarse
                    "08019 Barcelona",  # distrito 1, año 2022, debe descartarse (no es el más reciente)
                    "08900 Badalona",  # otro municipio, debe descartarse
                    "08019 Barcelona",  # distrito 1, otro indicador, debe descartarse
                ],
                "Distritos": [
                    None,
                    "0801901 Barcelona distrito 01",
                    "0801901 Barcelona distrito 01",
                    "0801901 Barcelona distrito 01",
                    "0890001 Badalona distrito 01",
                    "0801901 Barcelona distrito 01",
                ],
                "Secciones": [
                    None,
                    None,
                    "0801901001 Barcelona seccion 01001",
                    None,
                    None,
                    None,
                ],
                "Indicadores de renta media y mediana": [
                    "Renta neta media por persona",
                    "Renta neta media por persona",
                    "Renta neta media por persona",
                    "Renta neta media por persona",
                    "Renta neta media por persona",
                    "Renta mediana por persona",
                ],
                "Periodo": ["2023", "2023", "2023", "2022", "2023", "2023"],
                "Total": ["19.527", "13.990", "10.702", "13.500", "15.000", "11.200"],
            }
        )

    def test_filters_to_single_clean_row(self):
        result = build_district_income(self._raw_df())
        assert len(result) == 1
        row = result.iloc[0]
        assert row["codi_districte"] == 1
        assert row["renta_media"] == 13990.0
        assert row["periodo"] == 2023

    def test_raises_when_no_matching_rows(self):
        empty_df = self._raw_df()
        empty_df["Municipios"] = "09999 Otra Ciudad"
        with pytest.raises(ValueError):
            build_district_income(empty_df)


class TestBuildDistrictMobility:
    def test_filters_barcelona_and_aggregates(self):
        raw_df = pd.DataFrame(
            {
                "fecha": [20251015, 20251015, 20251015, 20251015],
                "destino": ["0801901", "0801901", "0801902", "01001"],  # última fila: fuera de Barcelona
                "viajes": [100.0, 50.0, 30.0, 999.0],
            }
        )
        result = build_district_mobility(raw_df)

        district_1 = result[result["codi_districte"] == 1].iloc[0]
        assert district_1["daily_foot_traffic"] == 150.0  # 100 + 50, la fila fuera de BCN no cuenta

        district_2 = result[result["codi_districte"] == 2].iloc[0]
        assert district_2["daily_foot_traffic"] == 30.0

    def test_raises_when_no_barcelona_rows(self):
        raw_df = pd.DataFrame({"fecha": [20251015], "destino": ["01001"], "viajes": [10.0]})
        with pytest.raises(ValueError):
            build_district_mobility(raw_df)


class TestReadRawMobility:
    def test_preserves_leading_zero_in_destino(self, tmp_path):
        # Regresión del bug real: sin dtype=str, pandas infiere 'destino'
        # como int64 y "0801901" se lee como 801901 (pierde el cero
        # inicial), rompiendo el filtro de prefijo "08019" de Barcelona.
        csv_path = tmp_path / "mobility.csv"
        csv_path.write_text("fecha|destino|viajes\n20251015|0801901|10.0\n", encoding="utf-8")

        df = read_raw_mobility(csv_path)

        assert df["destino"].iloc[0] == "0801901"


class TestReadRawCensus:
    def test_strips_bom_from_first_column(self, tmp_path):
        # Regresión del bug real: el censo comercial real trae BOM: sin
        # encoding="utf-8-sig", la primera columna se lee como
        # "\ufeffID_Global" en vez de "ID_Global", y build_competitors()
        # revienta con un KeyError al buscar la columna por su nombre limpio.
        csv_path = tmp_path / "census.csv"
        csv_path.write_bytes("ID_Global,Nom_Activitat\na1,Bars\n".encode("utf-8-sig"))

        df = read_raw_census(csv_path)

        assert df.columns[0] == "ID_Global"


class TestBuildCompetitors:
    def _raw_census_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "ID_Global": ["a1", "a2", "a3", "a4"],
                "Nom_Local": ["Bar Uno", "Tienda Ropa", "Bar Sin Coords", "Restaurant Dos"],
                "Nom_Activitat": ["Bars", "Vestir", "Bars", "Restaurants"],
                "Nom_Grup_Activitat": [
                    "Restaurants, bars i hotels",
                    "Comerç al detall",
                    "Restaurants, bars i hotels",
                    "Restaurants, bars i hotels",
                ],
                "Nom_Sector_Activitat": ["Serveis", "Serveis", "Serveis", "Serveis"],
                "Codi_Barri": [1, 2, 1, 3],
                "Nom_Barri": ["el Raval", "el Gotic", "el Raval", "Sant Pere"],
                "Codi_Districte": [1, 1, 1, 1],
                "Nom_Districte": ["Ciutat Vella"] * 4,
                "Latitud": [41.38, 41.38, None, 41.39],
                "Longitud": [2.17, 2.18, None, 2.19],
            }
        )

    def test_filters_hosteleria_and_drops_null_coords(self):
        result = build_competitors(self._raw_census_df())
        # a2 (Vestir, no es hostelería) y a3 (hostelería pero sin coords) deben quedar fuera
        assert set(result["id_global"]) == {"a1", "a4"}

    def test_districts_are_static_reference_list(self):
        result = build_districts()
        assert len(result) == 10
        assert set(result["codi_districte"]) == set(range(1, 11))

    def test_neighborhoods_derived_from_full_census(self):
        result = build_neighborhoods(self._raw_census_df())
        # 3 barrios distintos en el fixture (el Raval, el Gotic, Sant Pere),
        # incluyendo el de la tienda de ropa (no hostelería) — neighborhoods
        # se deriva del censo completo, no solo de los competidores.
        assert len(result) == 3