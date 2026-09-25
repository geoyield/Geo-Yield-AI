"""
==============================================================================
UNIT TESTS: GEOCODING API ROUTER
==============================================================================
File: tests/unit_tests/test_geocoding_router.py

Tests the FastAPI endpoint (`/api/geocodificar`).
Uses `patch` to mock both underlying services (Nominatim and AMB) to isolate 
the Router's orchestration logic from network constraints.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.api import app


class TestGeocodificar:
    def test_returns_full_suggestion_when_both_sources_succeed(self):
        """
        HAPPY PATH:
        Both the Text-to-Coordinates service and the Point-in-Polygon service 
        succeed. The endpoint must combine them into a single HTTP 200 payload.
        """
        with (
            patch(
                "backend.api.routers.geocoding.geocodificar_direccion",
                return_value={
                    "lat": 41.3806379,
                    "lon": 2.1731598,
                    "direccion_encontrada": "1-1B, Carrer de Sant Pau, el Raval, Ciutat Vella, Barcelona",
                    "codi_districte": 1,
                },
            ),
            patch(
                "backend.api.routers.geocoding.identificar_zona_pgm",
                return_value={"zona_pgm": "nucli_antic", "clau_urb": "12b"},
            ),
        ):
            client = TestClient(app)
            response = client.get("/api/geocode", params={"direccion": "Carrer de Sant Pau 1, Barcelona"})

        assert response.status_code == 200
        body = response.json()
        assert body["codi_districte"] == 1
        assert body["zona_pgm"] == "nucli_antic"
        assert body["clau_urb"] == "12b"

    def test_returns_404_when_address_not_found(self):
        """
        HARD FAILURE PATH:
        If Nominatim returns None, it means the address doesn't exist in Barcelona. 
        The Router MUST abort and return HTTP 404.
        """
        with patch("backend.api.routers.geocoding.geocodificar_direccion", return_value=None):
            client = TestClient(app)
            response = client.get("/api/geocode", params={"direccion": "esto no existe en ningún sitio"})

        assert response.status_code == 404

    def test_regression_degrades_gracefully_when_amb_service_fails(self):
        """
        GRACEFUL DEGRADATION TEST (Partial Failure):
        Regression: A real AMB timeout occurred during the API Spike session.
        If the Geocoder succeeds but the AMB fails, the Router MUST NOT drop the 
        successfully resolved District. It must return HTTP 200 with null zone fields.
        """
        with (
            patch(
                "backend.api.routers.geocoding.geocodificar_direccion",
                return_value={
                    "lat": 41.3921255,
                    "lon": 2.1658062,
                    "direccion_encontrada": "50, Passeig de Gràcia, l'Eixample, Barcelona",
                    "codi_districte": 2,
                },
            ),
            patch("backend.api.routers.geocoding.identificar_zona_pgm", return_value=None),
        ):
            client = TestClient(app)
            response = client.get("/api/geocode", params={"direccion": "Passeig de Gràcia 50, Barcelona"})

        assert response.status_code == 200
        body = response.json()
        assert body["codi_districte"] == 2
        assert body["zona_pgm"] is None
        assert body["clau_urb"] is None

    def test_regression_no_district_found_still_returns_coordinates(self):
        """
        GRACEFUL DEGRADATION TEST (Edge Case):
        If Nominatim finds coordinates but fails to map them to an official 
        District (e.g., an unmapped suburb), the endpoint must still return the 
        Lat/Lon so the Frontend Map can center on the pin.
        """
        with (
            patch(
                "backend.api.routers.geocoding.geocodificar_direccion",
                return_value={
                    "lat": 41.40,
                    "lon": 2.17,
                    "direccion_encontrada": "Alguna dirección, Barcelona",
                    "codi_districte": None,
                },
            ),
            patch("backend.api.routers.geocoding.identificar_zona_pgm", return_value=None),
        ):
            client = TestClient(app)
            response = client.get("/api/geocode", params={"direccion": "Alguna dirección, Barcelona"})

        assert response.status_code == 200
        body = response.json()
        assert body["codi_districte"] is None
        assert body["lat"] == 41.40

    def test_direccion_too_short_returns_422(self):
        """
        INPUT VALIDATION:
        Tests FastAPI/Pydantic automatic query validation (min_length=3).
        """
        client = TestClient(app)
        response = client.get("/api/geocode", params={"direccion": "ab"})
        assert response.status_code == 422