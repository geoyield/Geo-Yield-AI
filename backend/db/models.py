"""
==============================================================================
CORE DATABASE DOMAIN MODELS (ORM)
==============================================================================
File: backend/db/models.py

This module defines the relational, spatial, and vector schema of the project 
using SQLAlchemy. It integrates advanced PostgreSQL extensions such as:
- PostGIS (via GeoAlchemy2) for coordinate modeling and spatial calculations.
- pgvector for storage and similarity search of embeddings (RAG).
"""

from datetime import date, datetime

from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, ForeignKey, Numeric, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.rag.embeddings import EMBEDDING_DIM as LEGAL_EMBEDDING_DIM

from .base import Base

# ==============================================================================
# SOCIODEMOGRAPHIC AND SPATIAL LAYER (PHASE 1)
# ==============================================================================

class District(Base):
    """Base relational model for district-level aggregation."""
    __tablename__ = "districts"
    codi_districte: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nom_districte: Mapped[str] = mapped_column(String(100), nullable=False)


class Neighborhood(Base):
    """Hierarchical model subordinated to District."""
    __tablename__ = "neighborhoods"
    codi_barri: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nom_barri: Mapped[str] = mapped_column(String(100), nullable=False)
    codi_districte: Mapped[int] = mapped_column(SmallInteger, ForeignKey("districts.codi_districte"))


class Competitor(Base):
    """
    Represents geolocated commercial entities.
    Implements spatial data types (PostGIS) to enable native distance 
    calculations directly within the database layer.
    """
    __tablename__ = "competitors"
    id_global: Mapped[str] = mapped_column(String(64), primary_key=True)
    nom_activitat: Mapped[str] = mapped_column(String(255))
    nom_grup_activitat: Mapped[str] = mapped_column(String(255))
    codi_districte: Mapped[int] = mapped_column(SmallInteger, ForeignKey("districts.codi_districte"))
    codi_barri: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("neighborhoods.codi_barri"))

    # The use of 'Geography' with SRID 4326 allows for precise calculations in meters 
    # taking into account the Earth's curvature, rather than using flat geometric types.
    geom = mapped_column(Geography("POINT", srid=4326))
    loaded_at: Mapped[datetime] = mapped_column(server_default=func.now())


class DistrictIncome(Base):
    """"Economic metric aggregated by district."""
    __tablename__ = "district_income"
    codi_districte: Mapped[int] = mapped_column(SmallInteger, ForeignKey("districts.codi_districte"), primary_key=True)
    renta_media: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    periodo: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    loaded_at: Mapped[datetime] = mapped_column(server_default=func.now())


class DistrictMobility(Base):
    """Pedestrian traffic metric derived from mobility data."""
    __tablename__ = "district_mobility"
    codi_districte: Mapped[int] = mapped_column(SmallInteger, ForeignKey("districts.codi_districte"), primary_key=True)
    daily_foot_traffic: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    fecha: Mapped[date | None] = mapped_column(Date)
    loaded_at: Mapped[datetime] = mapped_column(server_default=func.now())


# ==============================================================================
# INFORMATION RETRIEVAL (RAG) AND NLP LAYER (PHASE 2)
# ==============================================================================

class LegalChunk(Base):
    """
    Vector storage model for normative text chunks.
    
    Refactoring Note (Migration 0005): 'numero_articulo' ceased to be the primary key.
    The complexity of urban legislation implies numbering collisions between 
    different norms (PGM, State Laws, Decrees). Domain uniqueness is now managed 
    via the tuple (fuente_legal, numero_articulo), operating under a synthetic primary key.
    """
    __tablename__ = "legal_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    fuente_legal: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    numero_articulo: Mapped[str] = mapped_column(String(20), nullable=False)
    titulo: Mapped[str] = mapped_column(String(500), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    expedient: Mapped[str | None] = mapped_column(String(100))
    versio: Mapped[str] = mapped_column(String(30), nullable=False)
    zona_pgm: Mapped[str | None] = mapped_column(String(50), index=True)
    documento_origen: Mapped[str | None] = mapped_column(String(255))

    # Cohesive Coupling: The vector dimension is not hardcoded here.
    # It directly depends on the embedding engine's configuration constant.
    embedding: Mapped[list[float]] = mapped_column(Vector(LEGAL_EMBEDDING_DIM), nullable=False)
    loaded_at: Mapped[datetime] = mapped_column(server_default=func.now())