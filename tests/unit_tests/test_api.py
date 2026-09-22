"""
Tests de los endpoints de FastAPI.

NOTA: /health es liveness puro y no toca la base de datos, así que se puede
testear sin una instancia de Postgres levantada (útil para CI). /ready sí
depende de la base de datos y se testeará con una BD real o un mock cuando
se construya la suite de integración (Fase 1 en adelante).
"""

from fastapi.testclient import TestClient

from backend.api.api import app


def test_health_returns_ok():
    # Se usa TestClient SIN "with": entrar como context manager dispara el
    # lifespan (startup/shutdown) de la app, que intenta conectar a
    # DATABASE_URL. /health es liveness puro y no debería depender de eso,
    # así que se testea sin ejecutar el startup — y de paso el test queda
    # a salvo de necesitar una Postgres real en la CI actual.
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
