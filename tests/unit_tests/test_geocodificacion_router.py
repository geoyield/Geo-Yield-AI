"""
Tests del router de geocodificación (backend/api/routers/geocodificacion.py).
Usa mocks sobre geocodificar_direccion e identificar_zona_pgm -- sin red
real hacia Nominatim ni el AMB.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.api import app


class TestGeocodificar:
    def test_returns_full_suggestion_when_both_sources_succeed(self):
        with (
            patch(
                "backend.api.routers.geocodificacion.geocodificar_direccion",
                return_value={
                    "lat": 41.3806379,
                    "lon": 2.1731598,
                    "direccion_encontrada": "1-1B, Carrer de Sant Pau, el Raval, Ciutat Vella, Barcelona",
                    "codi_districte": 1,
                },
            ),
            patch(
                "backend.api.routers.geocodificacion.identificar_zona_pgm",
                return_value={"zona_pgm": "nucli_antic", "clau_urb": "12b"},
            ),
        ):
            client = TestClient(app)
            response = client.get("/api/geocodificar", params={"direccion": "Carrer de Sant Pau 1, Barcelona"})

        assert response.status_code == 200
        body = response.json()
        assert body["codi_districte"] == 1
        assert body["zona_pgm"] == "nucli_antic"
        assert body["clau_urb"] == "12b"

    def test_returns_404_when_address_not_found(self):
        with patch("backend.api.routers.geocodificacion.geocodificar_direccion", return_value=None):
            client = TestClient(app)
            response = client.get("/api/geocodificar", params={"direccion": "esto no existe en ningún sitio"})

        assert response.status_code == 404

    def test_regression_degrades_gracefully_when_amb_service_fails(self):
        # Regresión: un timeout real del AMB ocurrió durante las pruebas
        # de esta sesión -- el distrito ya resuelto por geocodificación
        # no debe perderse solo porque el AMB no respondió. La respuesta
        # sigue siendo 200, con zona_pgm y clau_urb en null.
        with (
            patch(
                "backend.api.routers.geocodificacion.geocodificar_direccion",
                return_value={
                    "lat": 41.3921255,
                    "lon": 2.1658062,
                    "direccion_encontrada": "50, Passeig de Gràcia, l'Eixample, Barcelona",
                    "codi_districte": 2,
                },
            ),
            patch("backend.api.routers.geocodificacion.identificar_zona_pgm", return_value=None),
        ):
            client = TestClient(app)
            response = client.get("/api/geocodificar", params={"direccion": "Passeig de Gràcia 50, Barcelona"})

        assert response.status_code == 200
        body = response.json()
        assert body["codi_districte"] == 2
        assert body["zona_pgm"] is None
        assert body["clau_urb"] is None

    def test_regression_no_district_found_still_returns_coordinates(self):
        # Una dirección fuera de los límites que Nominatim reconoce como
        # distrito (o un suburb no reconocido) no debe hacer fallar todo
        # -- el mapa igual puede centrarse con lat/lon.
        with (
            patch(
                "backend.api.routers.geocodificacion.geocodificar_direccion",
                return_value={
                    "lat": 41.40,
                    "lon": 2.17,
                    "direccion_encontrada": "Alguna dirección, Barcelona",
                    "codi_districte": None,
                },
            ),
            patch("backend.api.routers.geocodificacion.identificar_zona_pgm", return_value=None),
        ):
            client = TestClient(app)
            response = client.get("/api/geocodificar", params={"direccion": "Alguna dirección, Barcelona"})

        assert response.status_code == 200
        body = response.json()
        assert body["codi_districte"] is None
        assert body["lat"] == 41.40

    def test_direccion_too_short_returns_422(self):
        client = TestClient(app)
        response = client.get("/api/geocodificar", params={"direccion": "ab"})
        assert response.status_code == 422