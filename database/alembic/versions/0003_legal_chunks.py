"""legal_chunks table for the RAG engine

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-16

Tabla que almacena un chunk por artículo de normativa (PGM de Barcelona,
portal NUMAMB), con su embedding para búsqueda por similitud.

Decisiones de diseño:
    - PK sobre `numero_articulo`: tras aplicar select_current_versions()
      (backend/rag/chunking.py) solo debe quedar UNA versión vigente por
      artículo, así que el número de artículo es una clave natural válida.
    - `embedding vector(384)`: dimensión de sentence-transformers/
      all-MiniLM-L6-v2 (decisión ya validada: embeddings locales, coste
      cero). Si el modelo de embeddings cambia en el futuro, esta columna
      necesitará una migración nueva (el ancho del vector es fijo).
    - Snapshot único (mismo criterio que Fase 1): cada ejecución del
      pipeline de ingesta reemplaza el contenido — no se versiona
      históricamente en esta tabla (el propio texto legal ya trae su
      histórico de modificaciones, no hace falta duplicarlo aquí).
"""

from typing import Sequence, Union

import geoalchemy2  # noqa: F401  (aunque no se usa aquí, mantiene consistencia con 0001)
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 384
# NOTA: se hardcodea a propósito, NO se importa de backend/rag/embeddings.py.
# Esta migración es una foto histórica de lo que era cierto en el momento
# en que se aplicó. Si en el futuro cambia el modelo de embeddings (y por
# tanto esta dimensión), esta migración ya aplicada no debe cambiar de
# comportamiento retroactivamente solo porque el código "vivo" cambió --
# para eso se añadiría una migración NUEVA (mismo patrón que 0002), nunca
# se edita una ya aplicada.


def upgrade() -> None:
    # Autosuficiente igual que en 0001: no asume que pgvector ya esté
    # habilitado, aunque en este caso normalmente ya lo estará (postgis
    # y pgvector se crean juntos en la 0001... salvo que esta migración se
    # aplique sobre una BD donde solo se aplicó 0001/0002 antes de que
    # pgvector se añadiera al proyecto).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "legal_chunks",
        sa.Column("numero_articulo", sa.String(length=20), nullable=False),
        sa.Column("titulo", sa.String(length=500), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("expedient", sa.String(length=100), nullable=True),
        sa.Column("versio", sa.String(length=30), nullable=False),
        sa.Column("documento_origen", sa.String(length=255), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("loaded_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("numero_articulo"),
    )

    # Índice HNSW para búsqueda por similitud coseno. A la escala del MVP
    # (cientos de artículos, no millones) un índice exacto sin approximate
    # search también sería viable, pero HNSW no cuesta nada de más aquí y
    # deja el camino preparado si el corpus crece a los 368 artículos
    # completos del Títol IV o más.
    op.execute(
        "CREATE INDEX idx_legal_chunks_embedding ON legal_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("idx_legal_chunks_embedding", table_name="legal_chunks")
    op.drop_table("legal_chunks")