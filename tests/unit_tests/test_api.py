"""
Tests básicos de la API (FastAPI).

El objetivo de este archivo es comprobar que la aplicación arranca bien
y responde a peticiones sencillas. Es nuestro test para confirmar que 
el servidor está vivo antes de meternos a probar cosas más complejas.
"""

from fastapi.testclient import TestClient

from backend.api.api import app


def test_health_returns_ok() -> None:
    """
    Comprueba que el endpoint /health devuelve un 200 OK.
    
    Nota técnica: 
    Instanciamos TestClient directamente en lugar de usar un bloque 'with'.
    Si usáramos 'with TestClient(app)', FastAPI ejecutaría el evento 'lifespan' 
    (arranque de la app) e intentaría conectarse a la base de datos PostgreSQL. 
    Como /health solo sirve para comprobar si la API está viva, lo probamos así 
    para aislar el test. Esto nos permite ejecutarlo rápido en la Integración 
    Continua (CI) sin necesidad de tener un Docker de Postgres levantado.
    """
    # 1. Preparamos el cliente de pruebas
    client = TestClient(app)

    # 2. Hacemos la petición GET al endpoint
    response = client.get("/health")

    # 3. Comprobamos que la respuesta es exactamente la esperada
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}