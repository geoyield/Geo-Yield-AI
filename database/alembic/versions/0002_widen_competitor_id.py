"""widen competitors.id_global to varchar(64)

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-09

El dataset real de Open Data BCN contiene valores de ID_Global de más de
36 caracteres (el largo estándar de un UUID) — detectado en una carga real
contra datos de producción, no en las pruebas con datos sintéticos. Se
ensancha la columna en vez de truncar o descartar esas filas.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "competitors",
        "id_global",
        existing_type=sa.String(length=36),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    # No se revierte a String(36): si ya se cargaron IDs de más de 36
    # caracteres, el downgrade truncaría datos reales sin avisar. Revertir
    # el ancho de columna sin pérdida de datos requeriría antes limpiar o
    # recortar manualmente las filas afectadas.
    op.alter_column(
        "competitors",
        "id_global",
        existing_type=sa.String(length=64),
        type_=sa.String(length=36),
        existing_nullable=False,
    )