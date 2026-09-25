"""
==============================================================================
ALEMBIC MIGRATION: RAG VECTOR TABLE (LEGAL CHUNKS)
==============================================================================
File: database/alembic/versions/0003_legal_chunks.py
Revision ID: 0003
Revises: 0002
Create Date: 2026-08-16

This migration creates the table responsible for storing the segmented legal 
articles (PGM of Barcelona) alongside their mathematical embeddings for 
semantic similarity search (RAG).

Design Decisions:
    - Primary Key (numero_articulo): After applying the versioning logic in 
      `chunking.py`, there is only ONE valid version per article. Therefore, 
      the article number acts as a valid natural key for the MVP.
    - `embedding vector(384)`: The dimension perfectly matches the local 
      Hugging Face model (`sentence-transformers/all-MiniLM-L6-v2`).
"""

from typing import Sequence, Union

# Imported to maintain consistency with spatial models, even if not explicitly used here
import geoalchemy2  # noqa: F401  
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ------------------------------------------------------------------------------
# IMMUTABILITY PRINCIPLE (Hardcoded Values)
# ------------------------------------------------------------------------------
EMBEDDING_DIM = 384
# Architectural Note: This is hardcoded ON PURPOSE. We DO NOT import this 
# constant from `backend.rag.embeddings`. 
# Why? Database migrations are historical snapshots. If next year we upgrade 
# our AI model to 768 dimensions and change the live Python code, doing so 
# would retroactively break this old migration file. To change dimensions in 
# the future, we must write a NEW migration file, never alter an applied one.


def upgrade() -> None:
    # Defensive Programming: Ensure pgvector is active before creating the table.
    # This prevents crashes if a developer runs this migration on a fresh DB.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "legal_chunks",
        sa.Column("numero_articulo", sa.String(length=20), nullable=False),
        sa.Column("titulo", sa.String(length=500), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("expedient", sa.String(length=100), nullable=True),
        sa.Column("versio", sa.String(length=30), nullable=False),
        sa.Column("documento_origen", sa.String(length=255), nullable=True),
        # Here we apply the pgvector custom SQLAlchemy type
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("loaded_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("numero_articulo"),
    )

    # ------------------------------------------------------------------------------
    # PERFORMANCE OPTIMIZATION: HNSW INDEX
    # ------------------------------------------------------------------------------
    # We create a Hierarchical Navigable Small World (HNSW) index using the 
    # specific 'vector_cosine_ops' operator. While an Exact Nearest Neighbor 
    # (KNN) search would work for a small MVP, setting up HNSW guarantees the 
    # semantic search will return in milliseconds even if we load the entire 
    # national legal code later on.
    op.execute(
        "CREATE INDEX idx_legal_chunks_embedding ON legal_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("idx_legal_chunks_embedding", table_name="legal_chunks")
    op.drop_table("legal_chunks")