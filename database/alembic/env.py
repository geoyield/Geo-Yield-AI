"""
Punto de Entrada (Entrypoint) del Motor de Migraciones (Alembic).

Este script actúa como el puente de configuración entre la herramienta de 
migraciones (Alembic) y la arquitectura de nuestro proyecto (FastAPI/SQLAlchemy).
Su principal responsabilidad es preparar el contexto de ejecución, cargar 
las variables de entorno desde la raíz y compartir la misma lógica de 
conexión que utiliza la API.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# -----------------------------------------------------------------------------
# INYECCIÓN DINÁMICA DEL CONTEXTO DE EJECUCIÓN
# -----------------------------------------------------------------------------
# Alembic se ejecuta desde su propia carpeta interna, por lo que no conoce 
# dónde está el código fuente de nuestra aplicación (backend). 
# Calculamos de forma dinámica la ruta de la raíz del proyecto (2 niveles arriba) 
# y la inyectamos en el PATH de Python (sys.path). Esto nos permite importar 
# nuestros modelos y librerías sin que Python lance un ImportError.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Cargamos el archivo .env principal del proyecto
load_dotenv(REPO_ROOT / ".env")

# Una vez ajustado el PATH, importamos nuestros metadatos y la función de conexión.
# (Se usa noqa: E402 para decirle al linter que ignoramos la regla de "imports 
# al principio del archivo", ya que era estrictamente necesario alterar el PATH primero).
from backend.db import Base  
from backend.db.connection import resolve_database_url  

config = context.config

# Configuramos el sistema de logs de Alembic
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# -----------------------------------------------------------------------------
# RESOLUCIÓN DE LA CONEXIÓN (Single Source of Truth)
# -----------------------------------------------------------------------------
# Principio DRY (Don't Repeat Yourself): En lugar de que Alembic tenga su propia 
# forma de leer variables y conectarse, reutilizamos `resolve_database_url()`.
# De esta forma, si cambiamos la red de Docker o la gestión de contraseñas, 
# la API y el motor de migraciones se actualizarán automáticamente sin divergir.
database_url = resolve_database_url()
config.set_main_option("sqlalchemy.url", database_url)

# Le pasamos a Alembic los metadatos de nuestros modelos (tablas) para que 
# pueda compararlos con la base de datos y detectar cambios (autogeneración).
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Ejecuta las migraciones en modo 'offline' (Sin conexión TCP).
    
    Este modo no aplica los cambios a la base de datos. En su lugar, lee 
    las migraciones y genera un script con las sentencias SQL resultantes. 
    Es muy útil para auditar qué sentencias SQL se van a ejecutar antes 
    de lanzarlas a un servidor de producción.
    """
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
    """
    Ejecuta las migraciones en modo 'online' (Transaccional).
    
    Crea una conexión directa a PostgreSQL, abre una transacción y aplica 
    todos los scripts de migración pendientes. Se usa NullPool para no 
    mantener conexiones abiertas innecesariamente, ya que este script 
    es efímero (se ejecuta y termina).
    """
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