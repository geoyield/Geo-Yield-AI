import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.db.connection import resolve_database_url

load_dotenv()


@pytest.fixture(scope="session")
def db_engine():
    try:
        url = resolve_database_url()
    except RuntimeError:
        pytest.skip("DATABASE_URL no definida: se omiten los tests que necesitan una base de datos real.")

    # Salvaguarda real, añadida tras perder datos reales en pruebas: esta
    # fixture TRUNCA legal_chunks entre tests. Si DATABASE_URL no deja
    # claro que apunta a una base de datos de pruebas (por convención,
    # que el nombre contenga "test"), los tests que la usan se SALTAN en
    # vez de arriesgarse a borrar contenido real -- así pasó una vez: los
    # 3 artículos del PGM cargados a mano desaparecieron sin aviso al
    # correr la suite contra la base de datos "de verdad".
    if "test" not in url.lower():
        pytest.skip(
            "DATABASE_URL no parece apuntar a una base de datos de pruebas "
            "(su nombre no contiene 'test'). Los tests de este módulo "
            "truncan legal_chunks entre ejecuciones -- para no arriesgar "
            "datos reales, se saltan hasta que DATABASE_URL apunte a una "
            "BD dedicada a tests (p. ej. 'geoyield_test')."
        )

    engine = create_engine(url, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"No se pudo conectar a la base de datos ({exc}); se omiten los tests que la necesitan.")
    return engine


@pytest.fixture
def db_session(db_engine):
    session = Session(db_engine)
    session.execute(text("TRUNCATE TABLE legal_chunks"))
    session.commit()
    yield session
    session.rollback()
    session.execute(text("TRUNCATE TABLE legal_chunks"))
    session.commit()
    session.close()