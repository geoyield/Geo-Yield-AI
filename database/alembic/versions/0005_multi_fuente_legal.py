"""support multiple legal sources, not just PGM

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-24

Hasta ahora `legal_chunks` solo contenía artículos del PGM, y
`numero_articulo` bastaba como clave primaria porque todos venían de la
misma fuente (nunca había dos "Article 302"). Al empezar a ingerir otras
normas (leyes estatales del BOE, órdenes y decretos de la Generalitat),
eso deja de ser cierto: una Orden del DOGC también tiene un "Artículo 1",
y colisionaría con cualquier otro "Artículo 1" de otra norma.

Cambios:
    - `fuente_legal`: identifica de qué norma viene cada artículo (p. ej.
      "PGM (Secció V)", "Ordre INT/358/2011"). Nunca nula.
    - La clave primaria pasa de `numero_articulo` a un `id` sintético
      (serial), con una restricción UNIQUE sobre (fuente_legal,
      numero_articulo) que preserva la garantía real de unicidad -- ya no
      es "un número de artículo no se repite", es "un número de artículo
      no se repite DENTRO de la misma norma".

Los 3 artículos del PGM ya cargados se backfillean con
fuente_legal = 'PGM (Secció V)' -- son, hasta ahora, los únicos.
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
    op.add_column("legal_chunks", sa.Column("fuente_legal", sa.String(length=255), nullable=True))
    op.execute(sa.text("UPDATE legal_chunks SET fuente_legal = :fuente WHERE fuente_legal IS NULL").bindparams(fuente=PGM_FUENTE_LEGAL))
    op.alter_column("legal_chunks", "fuente_legal", nullable=False)

    # numero_articulo deja de ser PK -- se sustituye por un id sintético.
    op.drop_constraint("legal_chunks_pkey", "legal_chunks", type_="primary")
    op.execute("ALTER TABLE legal_chunks ADD COLUMN id SERIAL PRIMARY KEY")

    op.create_unique_constraint(
        "uq_legal_chunks_fuente_numero", "legal_chunks", ["fuente_legal", "numero_articulo"]
    )
    op.create_index("ix_legal_chunks_fuente_legal", "legal_chunks", ["fuente_legal"])


def downgrade() -> None:
    op.drop_index("ix_legal_chunks_fuente_legal", table_name="legal_chunks")
    op.drop_constraint("uq_legal_chunks_fuente_numero", "legal_chunks", type_="unique")
    op.drop_column("legal_chunks", "id")
    op.create_primary_key("legal_chunks_pkey", "legal_chunks", ["numero_articulo"])
    op.drop_column("legal_chunks", "fuente_legal")