"""
Tests de backend/geo/amb_identify.py.
"""

from unittest.mock import MagicMock, patch

import requests

from backend.geo.amb_identify import _extraer_zona_de_resultados, identificar_zona_pgm

# Resultado real devuelto por el servicio Identify del AMB durante la
# investigación de esta sesión, para el centro de Barcelona (2.1734, 41.3851).
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
        # Regresión: la respuesta real de la investigación traía "5b" y
        # "5" (red viaria, sin normativa cargada) mezclados con "12b"
        # (sí tiene) -- debe encontrar 12b e ignorar el resto.
        resultado = _extraer_zona_de_resultados(RESULTADOS_REALES_CENTRO_BCN)
        assert resultado == {"zona_pgm": "nucli_antic", "clau_urb": "12b"}

    def test_ignores_road_network_codes(self):
        resultados = [{"attributes": {"CLAU_URB": "5"}}, {"attributes": {"CLAU_URB": "5b"}}]
        assert _extraer_zona_de_resultados(resultados) is None

    def test_returns_none_for_empty_results(self):
        assert _extraer_zona_de_resultados([]) is None

    def test_returns_none_for_unmapped_desenvolupament_code(self):
        # Regresión: un código real del PGM (no inventado) pero sin
        # normativa cargada -- no debe devolver una zona por error.
        resultados = [{"attributes": {"CLAU_URB": "22b"}}]
        assert _extraer_zona_de_resultados(resultados) is None

    def test_returns_none_when_attributes_missing(self):
        assert _extraer_zona_de_resultados([{"attributes": {}}]) is None


class TestIdentificarZonaPgmReintentos:
    @patch("backend.geo.amb_identify.time.sleep")
    @patch("backend.geo.amb_identify.requests.get")
    def test_regression_retries_on_timeout_then_succeeds(self, mock_get, mock_sleep):
        # Regresión: un timeout real ocurrió durante las pruebas de esta
        # sesión (el servicio público del AMB no siempre responde rápido)
        # -- debe reintentar en vez de fallar a la primera.
        respuesta_ok = MagicMock()
        respuesta_ok.json.return_value = {"results": [{"attributes": {"CLAU_URB": "12b"}}]}
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
        assert mock_get.call_count == 3  # intento inicial + 2 reintentos