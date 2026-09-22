"""
Tests del router de artículos (backend/api/routers/articulos.py). Usa
dependency_overrides para sustituir get_session -- sin BD real.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.api.api import app
from backend.api.deps import get_session


class FakeSession:
    def __init__(self, fila=None):
        self._fila = fila
        self.ultimos_params = None

    def execute(self, statement, params=None):
        self.ultimos_params = params
        result = MagicMock()
        result.mappings.return_value.first.return_value = self._fila
        return result


class TestObtenerArticulo:
    def test_returns_full_article_when_found(self):
        fila = {
            "fuente_legal": "PGM (Secció V)",
            "numero_articulo": "302",
            "titulo": "Zona de nucli antic",
            "contenido": "Texto completo del artículo 302.",
        }
        app.dependency_overrides[get_session] = lambda: FakeSession(fila)
        client = TestClient(app)
        response = client.get("/api/articulos", params={"fuente_legal": "PGM (Secció V)", "numero_articulo": "302"})
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json() == fila

    def test_regression_source_with_special_characters_in_query_param(self):
        # Regresión: fuentes como "Ley 22/2010 (Código de Consumo de
        # Cataluña)" traen "/" y paréntesis -- deben funcionar bien como
        # parámetro de consulta (el cliente HTTP los codifica), que es
        # justo la razón por la que no van en la ruta misma.
        fila = {
            "fuente_legal": "Ley 22/2010 (Código de Consumo de Cataluña)",
            "numero_articulo": "111-1",
            "titulo": "Objeto y ámbito",
            "contenido": "Texto de prueba.",
        }
        app.dependency_overrides[get_session] = lambda: FakeSession(fila)
        client = TestClient(app)
        response = client.get(
            "/api/articulos",
            params={"fuente_legal": "Ley 22/2010 (Código de Consumo de Cataluña)", "numero_articulo": "111-1"},
        )
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["fuente_legal"] == "Ley 22/2010 (Código de Consumo de Cataluña)"

    def test_returns_404_when_article_not_found(self):
        app.dependency_overrides[get_session] = lambda: FakeSession(None)
        client = TestClient(app)
        response = client.get("/api/articulos", params={"fuente_legal": "No existe", "numero_articulo": "1"})
        app.dependency_overrides.clear()

        assert response.status_code == 404

    def test_regression_whitespace_only_value_returns_422_not_a_db_lookup(self):
        # Regresión: Query(..., min_length=1) de Pydantic solo valida la
        # longitud del string ANTES de limpiar espacios -- un valor de
        # " " (un espacio) tiene longitud 1 y pasa esa validación, pero
        # tras strip() queda vacío. Sin la comprobación explícita tras
        # limpiar, esto llegaría silenciosamente hasta la consulta SQL en
        # vez de fallar con un mensaje claro.
        app.dependency_overrides[get_session] = lambda: FakeSession(None)
        client = TestClient(app)
        response = client.get("/api/articulos", params={"fuente_legal": " ", "numero_articulo": "302"})
        app.dependency_overrides.clear()

        assert response.status_code == 422
        assert "no pueden estar vacíos" in response.json()["detail"]

    def test_regression_leading_trailing_whitespace_is_stripped_before_lookup(self):
        # La búsqueda usa los valores ya limpios, no los crudos -- una
        # cita con espacios accidentales al inicio o final (p. ej. de un
        # copiar/pegar) sigue encontrando el artículo correcto. Se
        # comprueba contra los parámetros reales que llegan a execute(),
        # no solo el código de estado -- con el FakeSession anterior
        # (que ignoraba los parámetros) este test podía pasar aunque el
        # strip() no existiera.
        fila = {
            "fuente_legal": "PGM (Secció V)",
            "numero_articulo": "302",
            "titulo": "Zona de nucli antic",
            "contenido": "Texto completo.",
        }
        fake_session = FakeSession(fila)
        app.dependency_overrides[get_session] = lambda: fake_session
        client = TestClient(app)
        response = client.get(
            "/api/articulos", params={"fuente_legal": "  PGM (Secció V)  ", "numero_articulo": " 302 "}
        )
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert fake_session.ultimos_params == {"fuente": "PGM (Secció V)", "numero": "302"}