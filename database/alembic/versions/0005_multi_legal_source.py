"""
==============================================================================
ALEMBIC MIGRATION: MULTI-SOURCE LEGAL CORPUS
==============================================================================
File: database/alembic/versions/0005_multi_legal_source.py
Revision ID: 0005
Revises: 0004
Create Date: 2026-08-24

Architectural Refactoring: 
Resolves the Technical Debt introduced in Migration 0003. 
Initially, `numero_articulo` was used as the Primary Key because we only 
ingested the PGM. To support National (BOE) and Regional (DOGC) laws, this 
must change, as 'Article 1' of the BOE would collide with 'Article 1' of the PGM.

Changes:
    1. Adds `fuente_legal` column to identify the source of the law.
    2. Swaps the natural Primary Key for a surrogate `SERIAL` ID.
    3. Adds a Composite Unique Constraint to maintain data integrity.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PGM_FUENTE_LEGAL = "PGM (Secció V)"


def upgrade() -> None:
    # ------------------------------------------------------------------------------
    # ZERO-DOWNTIME BACKFILL PATTERN
    # ------------------------------------------------------------------------------
    # Step 1: Add the new column allowing NULLs (otherwise Postgres rejects it on tables with data)
    op.add_column("legal_chunks", sa.Column("fuente_legal", sa.String(length=255), nullable=True))

    # Step 2: Backfill existing rows with the default PGM value
    op.execute(sa.text("UPDATE legal_chunks SET fuente_legal = :fuente WHERE fuente_legal IS NULL").bindparams(fuente=PGM_FUENTE_LEGAL))

    # Step 3: Harden the schema by enforcing NOT NULL
    op.alter_column("legal_chunks", "fuente_legal", nullable=False)

    # ------------------------------------------------------------------------------
    # PRIMARY KEY REFACTORING
    # ------------------------------------------------------------------------------
    # Drop the old natural key constraint
    op.drop_constraint("legal_chunks_pkey", "legal_chunks", type_="primary")
    # Add a surrogate auto-incrementing integer key
    op.execute("ALTER TABLE legal_chunks ADD COLUMN id SERIAL PRIMARY KEY")

    # Enforce Business Logic: An article number cannot repeat WITHIN the same law.
    op.create_unique_constraint(
        "uq_legal_chunks_fuente_numero", "legal_chunks", ["fuente_legal", "numero_articulo"]
    )

    # Add an index for faster RAG filtering by legal source
    op.create_index("ix_legal_chunks_fuente_legal", "legal_chunks", ["fuente_legal"])


def downgrade() -> None:
    op.drop_index("ix_legal_chunks_fuente_legal", table_name="legal_chunks")
    op.drop_constraint("uq_legal_chunks_fuente_numero", "legal_chunks", type_="unique")
    op.drop_column("legal_chunks", "id")
    # Restore the old natural key
    op.create_primary_key("legal_chunks_pkey", "legal_chunks", ["numero_articulo"])
    op.drop_column("legal_chunks", "fuente_legal")