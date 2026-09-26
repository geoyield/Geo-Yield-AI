"""
==============================================================================
DATABASE MIGRATION: ADDING PGM ZONING METADATA
==============================================================================
Revision ID: 0004
Revises: 0003
Create Date: 2026-08-18

Adds the urban zoning classification (PGM) to each legal chunk.
This enables EXACT filtering based on the zone selected by the user in Phase 3,
combined with semantic search (the exact type of hybrid structured+vectorial 
intersection that justified choosing pgvector in ADR 0001).

Only the 3 currently loaded articles (302, 303, 311) are backfilled. 
The possible values for zona_pgm are a subset of the actual PGM classification
(Article 314, Chapter 4) — it will be expanded as more articles from Section V 
are ingested. There is no need to anticipate the ~9 zones we haven't indexed yet.
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
    # 1. Schema Migration (DDL): Add the column and a B-Tree index for fast pre-filtering
    op.add_column("legal_chunks", sa.Column("zona_pgm", sa.String(length=50), nullable=True))
    op.create_index("ix_legal_chunks_zona_pgm", "legal_chunks", ["zona_pgm"])

    # 2. Data Migration (Backfill): Populate the new column for historically ingested records
    #    using the mapping defined in the chunking business logic.
    connection = op.get_bind()
    for numero_articulo, zona in ARTICLE_TO_ZONA_PGM.items():
        connection.execute(
            sa.text("UPDATE legal_chunks SET zona_pgm = :zona WHERE numero_articulo = :numero"),
            {"zona": zona, "numero": numero_articulo},
        )


def downgrade() -> None:
    # Rollback operations in reverse order to ensure data consistency
    op.drop_index("ix_legal_chunks_zona_pgm", table_name="legal_chunks")
    op.drop_column("legal_chunks", "zona_pgm")
