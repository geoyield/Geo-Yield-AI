"""
==============================================================================
API SCHEMAS (DTO): LEGAL ARTICLE VIEWER
==============================================================================
File: backend/api/schemas/articles.py

Defines the outbound Data Transfer Object (DTO) for the raw legal article viewer.
"""

from pydantic import BaseModel, ConfigDict


class ArticuloOut(BaseModel):
    """
    Outbound DTO for a legal article.
    
    Security Design (Data Leakage Prevention):
    `extra="forbid"` acts as an outbound firewall. If a developer accidentally 
    modifies the SQL query in `routers/articulos.py` to `SELECT * FROM legal_chunks`, 
    the database would return internal metadata (like `expedient` or `loaded_at`), 
    and more critically, the massive 384-dimensional `embedding` float array. 
    If Pydantic allowed extra fields, FastAPI would silently serialize and leak 
    this heavy mathematical data to the Frontend. 
    By setting `extra="forbid"`, Pydantic will intentionally crash and throw a 
    500 Server Error if it detects unexpected columns, preventing Data Leakage.
    """
    model_config = ConfigDict(extra="forbid")

    fuente_legal: str
    numero_articulo: str
    titulo: str
    contenido: str