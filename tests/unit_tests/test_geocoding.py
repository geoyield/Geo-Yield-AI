"""
==============================================================================
UNIT TESTS: GEOCODING PARSER
==============================================================================
File: tests/unit_tests/test_geocoding.py

Tests the lexical normalization logic (`resolver_distrito_desde_suburb`).
Note (Test Boundaries): `geocodificar_direccion` is NOT tested here because 
it makes real HTTP network calls to Nominatim. Unit tests must remain fast, 
deterministic, and isolated from external networks.
"""

from backend.geo.geocoding import resolver_distrito_desde_suburb


class TestResolverDistritoDesdeSuburb:
    def test_exact_match_without_article(self):
        assert resolver_distrito_desde_suburb("Ciutat Vella") == 1
        assert resolver_distrito_desde_suburb("Sant Martí") == 10

    def test_regression_les_corts_keeps_its_les(self):
        """
        REGRESSION TEST (Safety Net):
        'Les Corts' is the official proper noun. 'Les' is not a disposable article 
        here, unlike 'l'Eixample'. If future refactoring applies Regex stripping 
        blindly before attempting an exact match, 'Les Corts' would become 'Corts' 
        and fail silently. This test prevents that regression.
        """
        assert resolver_distrito_desde_suburb("Les Corts") == 4

    def test_strips_leading_apostrophe_article(self):     
        assert resolver_distrito_desde_suburb("l'Eixample") == 2

    def test_strips_leading_la_article(self):
        # Hypothetical variant to ensure full regex coverage
        assert resolver_distrito_desde_suburb("la Eixample") == 2  

    def test_case_insensitive(self):
        assert resolver_distrito_desde_suburb("CIUTAT VELLA") == 1
        assert resolver_distrito_desde_suburb("l'eixample") == 2

    def test_returns_none_for_unknown_suburb(self):
        """
        FAIL-SAFE ENFORCEMENT:
        Ensures the system does not 'guess' or hallucinate IDs for unknown regions.
        """
        assert resolver_distrito_desde_suburb("El Raval") is None  # Neighborhood, not district
        assert resolver_distrito_desde_suburb("Madrid") is None

    def test_returns_none_for_empty_or_none(self):
        assert resolver_distrito_desde_suburb(None) is None
        assert resolver_distrito_desde_suburb("") is None

    def test_regression_real_nominatim_responses(self):
        # Empirical test cases based on actual payloads returned by Nominatim 
        # during the 'probar_geocodificacion.py' API Spike phase.
        assert resolver_distrito_desde_suburb("Ciutat Vella") == 1
        assert resolver_distrito_desde_suburb("Sant Martí") == 10
        assert resolver_distrito_desde_suburb("l'Eixample") == 2