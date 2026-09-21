"""add zona_pgm to legal_chunks

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-18

Añade la clasificación de zona urbanística (PGM) a cada artículo legal,
para poder filtrar de forma EXACTA por la zona que el usuario elige en la
Fase 3, combinado con la búsqueda semántica (justo el tipo de cruce
híbrido estructurado+vectorial por el que se eligió pgvector en el ADR
0001).

Solo se backfillean los 3 artículos ya cargados (302, 303, 311). Los
valores de zona_pgm posibles son un subconjunto de la clasificación real
del PGM (Article 314, Capítol 4) — se amplía según se vayan ingiriendo más
artículos de la Secció V, no hace falta anticipar aquí las ~9 zonas que
todavía no tenemos indexadas.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.rag.chunking import ARTICLE_TO_ZONA_PGM

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("legal_chunks", sa.Column("zona_pgm", sa.String(length=50), nullable=True))
    op.create_index("ix_legal_chunks_zona_pgm", "legal_chunks", ["zona_pgm"])

    connection = op.get_bind()
    for numero_articulo, zona in ARTICLE_TO_ZONA_PGM.items():
        connection.execute(
            sa.text("UPDATE legal_chunks SET zona_pgm = :zona WHERE numero_articulo = :numero"),
            {"zona": zona, "numero": numero_articulo},
        )


def downgrade() -> None:
    op.drop_index("ix_legal_chunks_zona_pgm", table_name="legal_chunks")
    op.drop_column("legal_chunks", "zona_pgm")
