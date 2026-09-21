"""
Base declarativa compartida por todos los modelos ORM de Geo-Yield-AI.

Se mantiene en un módulo separado de `models.py` para que Alembic pueda
importar `Base.metadata` sin arrastrar el resto de dependencias de la
aplicación (evita imports circulares entre `backend.api.api` y `backend.db`).
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
