"""
Entrypoint de Alembic.

Se ejecuta desde la raíz del repo con:
    alembic -c database/alembic.ini upgrade head

Resuelve DATABASE_URL desde el .env de la raíz (no desde alembic.ini) para
tener una única fuente de verdad de la cadena de conexión, compartida con
backend/api/api.py y docker-compose.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# La raíz del repo es dos niveles por encima de este fichero
# (database/alembic/env.py -> database/ -> raíz).
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

from backend.db import Base  # noqa: E402  (import tras ajustar sys.path)
from backend.db.connection import resolve_database_url  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Ver backend/db/connection.py: DATABASE_URL apunta a "postgis" (nombre del
# servicio en la red de docker-compose); DB_HOST_OVERRIDE=localhost permite
# ejecutar Alembic desde el host. La misma variable la usa también
# database/load_to_db.py, por eso vive en un helper compartido.
database_url = resolve_database_url()
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera el SQL de la migración sin conectar a la base de datos."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica la migración conectando directamente a la base de datos."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()