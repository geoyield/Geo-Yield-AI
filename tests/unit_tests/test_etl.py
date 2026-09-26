"""
==============================================================================
UNIT TESTS: ETL PIPELINES
==============================================================================
File: tests/unit_tests/test_etl.py

Tests the ETL transformations for the Competitors, Income, and Mobility datasets.
Instead of reading the massive real CSV files, these tests use synthetic 
in-memory Pandas DataFrames. This ensures tests are deterministic, fast, 
and independent of local data files ignored by Git.
"""

import pandas as pd
import pytest

from backend.etl.competitors import build_competitors, build_districts, build_neighborhoods, read_raw_census
from backend.etl.income import _extract_district_number, _parse_spanish_number, build_district_income
from backend.etl.mobility import build_district_mobility, read_raw_mobility


class TestParseSpanishNumber:
    def test_thousands_separator_with_trailing_zero(self):
        """
        Regression Test: Verifies the fix for the silent bug where Pandas inferred 
        "13.990" (13,990 Euros) as a float (13.99), dropping the trailing zero forever.
        Our custom parser MUST return the correct integer magnitude.
        """
        assert _parse_spanish_number("13.990") == 13990.0

    def test_thousands_separator_no_trailing_zero(self):
        """Verifies standard Spanish formatting parsing."""
        assert _parse_spanish_number("21.976") == 21976.0

    def test_nan_passthrough(self):
        """Verifies that missing values are handled gracefully."""
        assert pd.isna(_parse_spanish_number(float("nan")))


class TestExtractDistrictNumber:
    def test_extracts_number(self):
        """Verifies Regex extraction of the District ID from dirty government strings."""
        assert _extract_district_number("0801901 Barcelona distrito 01") == 1
        assert _extract_district_number("0801910 Barcelona distrito 10") == 10

    def test_returns_none_when_missing(self):
        assert _extract_district_number(float("nan")) is None


class TestBuildDistrictIncome:
    def _raw_df(self) -> pd.DataFrame:
        """Helper method: Creates a synthetic, dirty DataFrame mirroring the INE format."""
        return pd.DataFrame(
            {
                "Municipios": [
                    "08019 Barcelona",  # Keep: Total municipality (will be filtered out by level)
                    "08019 Barcelona",  # KEEP: District 1, 2023
                    "08019 Barcelona",  # Filter: Census section level
                    "08019 Barcelona",  # Filter: Old year (2022)
                    "08900 Badalona",   # Filter: Wrong municipality
                    "08019 Barcelona",  # Filter: Wrong indicator
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
        """Ensures the complex boolean filtering isolates the exact correct row."""
        result = build_district_income(self._raw_df())
        assert len(result) == 1
        row = result.iloc[0]
        assert row["codi_districte"] == 1
        assert row["renta_media"] == 13990.0
        assert row["periodo"] == 2023

    def test_raises_when_no_matching_rows(self):
        """Fail-Fast principle: Pipeline must crash if filter logic yields empty results."""
        empty_df = self._raw_df()
        empty_df["Municipios"] = "09999 Otra Ciudad"
        with pytest.raises(ValueError):
            build_district_income(empty_df)


class TestBuildDistrictMobility:
    def test_filters_barcelona_and_aggregates(self):
        """Verifies spatial filtering (starts with 08019) and trip aggregation."""
        raw_df = pd.DataFrame(
            {
                "fecha": [20251015, 20251015, 20251015, 20251015],
                "destino": ["0801901", "0801901", "0801902", "01001"],  # Last row is outside BCN
                "viajes": [100.0, 50.0, 30.0, 999.0],
            }
        )
        result = build_district_mobility(raw_df)

        district_1 = result[result["codi_districte"] == 1].iloc[0]
        assert district_1["daily_foot_traffic"] == 150.0  # 100 + 50 (ignoring outside trips)

        district_2 = result[result["codi_districte"] == 2].iloc[0]
        assert district_2["daily_foot_traffic"] == 30.0

    def test_raises_when_no_barcelona_rows(self):
        raw_df = pd.DataFrame({"fecha": [20251015], "destino": ["01001"], "viajes": [10.0]})
        with pytest.raises(ValueError):
            build_district_mobility(raw_df)


class TestReadRawMobility:
    def test_preserves_leading_zero_in_destino(self, tmp_path):
        """
        Regression Test: Verifies the fix for the 'Lost Zero' bug.
        The ETL MUST use `dtype=str` to prevent Pandas from casting '0801901' to '801901'.
        """
        csv_path = tmp_path / "mobility.csv"
        csv_path.write_text("fecha|destino|viajes\n20251015|0801901|10.0\n", encoding="utf-8")

        df = read_raw_mobility(csv_path)

        assert df["destino"].iloc[0] == "0801901"


class TestReadRawCensus:
    def test_strips_bom_from_first_column(self, tmp_path):
        """
        Regression Test: Verifies the fix for the hidden Byte Order Mark (BOM).
        The ETL MUST use `encoding="utf-8-sig"` to prevent the first column 
        from being read as '\\ufeffID_Global'.
        """
        csv_path = tmp_path / "census.csv"
        csv_path.write_bytes("ID_Global,Nom_Activitat\na1,Bars\n".encode("utf-8-sig"))

        df = read_raw_census(csv_path)

        assert df.columns[0] == "ID_Global"


class TestBuildCompetitors:
    def _raw_census_df(self) -> pd.DataFrame:
        """Helper method: Creates synthetic commercial census data."""
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
        # a2 (Clothes, not hospitality) and a3 (hospitality but missing coords) must be dropped
        assert set(result["id_global"]) == {"a1", "a4"}

    def test_districts_are_static_reference_list(self):
        """Verifies architectural decision: Districts must be static, not derived."""
        result = build_districts()
        assert len(result) == 10
        assert set(result["codi_districte"]) == set(range(1, 11))

    def test_neighborhoods_derived_from_full_census(self):
        result = build_neighborhoods(self._raw_census_df())
        # The 'Clothes' shop is in 'el Gotic'. Neighborhoods should be derived 
        # from the FULL census, not just the hospitality competitors.
        assert len(result) == 3