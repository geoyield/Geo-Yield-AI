"""
==============================================================================
UNIT TESTS: AMB GIS SERVICE WRAPPER
==============================================================================
File: tests/unit_tests/test_amb_identify.py

Tests the translation between AMB's raw GIS payloads and internal RAG zoning codes.
Uses Python's `unittest.mock` to simulate HTTP requests, ensuring the test suite 
remains deterministic and independent of the external government server's uptime.
"""

from unittest.mock import MagicMock, patch

import requests

from backend.geo.amb_identify import _extraer_zona_de_resultados, identificar_zona_pgm

# Empirical payload returned by the AMB Identify service during the API Spike 
# session, querying the center of Barcelona (Plaça Catalunya: 2.1734, 41.3851).
RESULTADOS_REALES_CENTRO_BCN = [
    {"layerId": 1, "attributes": {"CLAU_URB": "5b"}},
    {"layerId": 1, "attributes": {"CLAU_URB": "12b"}},
    {"layerId": 1, "attributes": {"CLAU_URB": "12b"}},
    {"layerId": 2, "attributes": {"CLAU_URB": "5b"}},
    {"layerId": 2, "attributes": {"CLAU_URB": "12b"}},
    {"layerId": 2, "attributes": {"CLAU_URB": "5"}},
]


class TestExtraerZonaDeResultados:
    def test_regression_real_amb_response_finds_nucli_antic(self):
        """
        REGRESSION TEST (Noise Filtering):
        The real AMB response mixes unmapped road network codes ("5b", "5") 
        with valid urban zones ("12b"). The parser must ignore the unmapped 
        noise and successfully extract the valid '12b' (nucli_antic).
        """
        resultado = _extraer_zona_de_resultados(RESULTADOS_REALES_CENTRO_BCN)
        assert resultado == {"zona_pgm": "nucli_antic", "clau_urb": "12b"}

    def test_ignores_road_network_codes(self):
        resultados = [{"attributes": {"CLAU_URB": "5"}}, {"attributes": {"CLAU_URB": "5b"}}]
        assert _extraer_zona_de_resultados(resultados) is None

    def test_returns_none_for_empty_results(self):
        assert _extraer_zona_de_resultados([]) is None

    def test_returns_none_for_unmapped_desenvolupament_code(self):
        """
        ALLOW-LIST ENFORCEMENT:
        "22b" is a real PGM code, but we haven't ingested its legal text yet.
        The system MUST return None to prevent the AI from hallucinating rules 
        for a zone it doesn't know about.
        """
        resultados = [{"attributes": {"CLAU_URB": "22b"}}]
        assert _extraer_zona_de_resultados(resultados) is None

    def test_returns_none_when_attributes_missing(self):
        assert _extraer_zona_de_resultados([{"attributes": {}}]) is None


class TestIdentificarZonaPgmReintentos:
    # Applying Decorators to intercept external dependencies
    @patch("backend.geo.amb_identify.time.sleep")
    @patch("backend.geo.amb_identify.requests.get")
    def test_regression_retries_on_timeout_then_succeeds(self, mock_get, mock_sleep):
        """
        STATE MACHINE VERIFICATION (Resilience):
        Simulates a transient network failure (Timeout) on the first call, 
        followed by a successful response on the second call. Proves the retry 
        loop recovers gracefully.
        """
        respuesta_ok = MagicMock()
        respuesta_ok.json.return_value = {"results": [{"attributes": {"CLAU_URB": "12b"}}]}

        # side_effect allows us to define a sequence of returns for consecutive calls
        mock_get.side_effect = [requests.exceptions.ReadTimeout("timeout simulado"), respuesta_ok]

        resultado = identificar_zona_pgm(41.3851, 2.1734)

        assert resultado == {"zona_pgm": "nucli_antic", "clau_urb": "12b"}
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once()

    @patch("backend.geo.amb_identify.time.sleep")
    @patch("backend.geo.amb_identify.requests.get")
    def test_gives_up_after_max_retries_and_returns_none(self, mock_get, mock_sleep):
        mock_get.side_effect = requests.exceptions.ReadTimeout("timeout simulado")

        resultado = identificar_zona_pgm(41.3851, 2.1734)

        assert resultado is None
        assert mock_get.call_count == 3  # Initial attempt + 2 retries