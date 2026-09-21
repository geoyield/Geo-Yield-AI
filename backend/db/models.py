from datetime import date, datetime

from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, ForeignKey, Numeric, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.rag.embeddings import EMBEDDING_DIM as LEGAL_EMBEDDING_DIM

from .base import Base


class District(Base):
    __tablename__ = "districts"
    codi_districte: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nom_districte: Mapped[str] = mapped_column(String(100), nullable=False)


class Neighborhood(Base):
    __tablename__ = "neighborhoods"
    codi_barri: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nom_barri: Mapped[str] = mapped_column(String(100), nullable=False)
    codi_districte: Mapped[int] = mapped_column(SmallInteger, ForeignKey("districts.codi_districte"))


class Competitor(Base):
    __tablename__ = "competitors"
    id_global: Mapped[str] = mapped_column(String(64), primary_key=True)
    nom_activitat: Mapped[str] = mapped_column(String(255))
    nom_grup_activitat: Mapped[str] = mapped_column(String(255))
    codi_districte: Mapped[int] = mapped_column(SmallInteger, ForeignKey("districts.codi_districte"))
    codi_barri: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("neighborhoods.codi_barri"))
    geom = mapped_column(Geography("POINT", srid=4326))
    loaded_at: Mapped[datetime] = mapped_column(server_default=func.now())


class DistrictIncome(Base):
    __tablename__ = "district_income"
    codi_districte: Mapped[int] = mapped_column(SmallInteger, ForeignKey("districts.codi_districte"), primary_key=True)
    renta_media: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    periodo: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    loaded_at: Mapped[datetime] = mapped_column(server_default=func.now())


class DistrictMobility(Base):
    __tablename__ = "district_mobility"
    codi_districte: Mapped[int] = mapped_column(SmallInteger, ForeignKey("districts.codi_districte"), primary_key=True)
    daily_foot_traffic: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    fecha: Mapped[date | None] = mapped_column(Date)
    loaded_at: Mapped[datetime] = mapped_column(server_default=func.now())


class LegalChunk(Base):
    """
    numero_articulo ya NO es la clave primaria (migración 0005): con
    varias normas de origen (PGM, leyes estatales, órdenes/decretos de la
    Generalitat), el mismo número de artículo puede repetirse entre
    normas distintas. La clave primaria es un `id` sintético; la
    unicidad real se garantiza con (fuente_legal, numero_articulo).
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
    embedding: Mapped[list[float]] = mapped_column(Vector(LEGAL_EMBEDDING_DIM), nullable=False)
    loaded_at: Mapped[datetime] = mapped_column(server_default=func.now())