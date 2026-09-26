"""
==============================================================================
BASE DECLARATIVA ORM (SQLAlchemy)
==============================================================================
Archivo: backend/db/base.py

Esta es la clase padre de la que heredan todos los modelos de base de datos
(District, Competitor, LegalChunk). 

Aprendizaje de diseño de software:
Decidimos poner esta clase en su propio archivo 
y no en `models.py`. Si estuviera en `models.py`, la herramienta de migraciones 
Alembic tendría que importar todo ese archivo gigante. Como nuestros modelos incluyen 
tablas de IA, importar `models.py` obligaría a cargar dependencias pesadas 
de Machine Learning (embeddings) solo para poder leer el esquema de la base 
de datos. Separar la 'Base' aquí evita imports circulares y acoplamientos 
innecesarios entre la capa de base de datos y la capa de IA.
"""

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """
    Clase registro (Registry) de SQLAlchemy. 
    Vigila y almacena la estructura (metadata) de toda clase que herede de ella.
    """
    pass
