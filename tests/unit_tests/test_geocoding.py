"""
Tests de backend/geo/geocoding.py. Solo cubre resolver_distrito_desde_suburb
(la lógica de emparejamiento) -- geocodificar_direccion en sí depende de
red real hacia Nominatim, y no se prueba aquí.
"""

from backend.geo.geocoding import resolver_distrito_desde_suburb


class TestResolverDistritoDesdeSuburb:
    def test_exact_match_without_article(self):
        assert resolver_distrito_desde_suburb("Ciutat Vella") == 1
        assert resolver_distrito_desde_suburb("Sant Martí") == 10

    def test_regression_les_corts_keeps_its_les(self):
        # Regresión: "Les Corts" es el nombre oficial completo -- "Les"
        # no es un artículo que sobra aquí, a diferencia de "l'Eixample".
        # Si la lógica quitara artículos a ciegas antes de intentar una
        # coincidencia exacta, esto se convertiría en "Corts" y fallaría.
        assert resolver_distrito_desde_suburb("Les Corts") == 4

    def test_strips_leading_apostrophe_article(self):
        assert resolver_distrito_desde_suburb("l'Eixample") == 2

    def test_strips_leading_la_article(self):
        assert resolver_distrito_desde_suburb("la Eixample") == 2  # variante hipotética, por si acaso

    def test_case_insensitive(self):
        assert resolver_distrito_desde_suburb("CIUTAT VELLA") == 1
        assert resolver_distrito_desde_suburb("l'eixample") == 2

    def test_returns_none_for_unknown_suburb(self):
        assert resolver_distrito_desde_suburb("El Raval") is None  # barrio, no distrito
        assert resolver_distrito_desde_suburb("Madrid") is None

    def test_returns_none_for_empty_or_none(self):
        assert resolver_distrito_desde_suburb(None) is None
        assert resolver_distrito_desde_suburb("") is None

    def test_regression_real_nominatim_responses(self):
        # Casos reales devueltos por Nominatim durante la investigación
        # de esta sesión, para las 3 direcciones de prueba.
        assert resolver_distrito_desde_suburb("Ciutat Vella") == 1
        assert resolver_distrito_desde_suburb("Sant Martí") == 10
        assert resolver_distrito_desde_suburb("l'Eixample") == 2