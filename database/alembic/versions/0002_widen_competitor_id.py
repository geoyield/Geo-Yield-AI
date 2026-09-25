"""
==============================================================================
MIGRACIÓN 0002: RESIZE COLUMNA ID (FASE 1)
==============================================================================
Revision ID: 0002
Revises: 0001
Create Date: 2026-08-09

Esta migración refleja un problema clásico al pasar de entornos de desarrollo 
(con datos sintéticos) a producción (con Open Data BCN real). 

Inicialmente definimos `id_global` en 36 caracteres asumiendo que siempre 
sería un UUID estándar. Sin embargo, al lanzar el script ETL contra el censo 
comercial del ayuntamiento, descubrimos registros con identificadores más largos. 
En lugar de truncar la información original (lo cual rompería la trazabilidad), 
la solución fue ensanchar el tipo de dato de la columna.
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
    # Aunque el código para revertir el esquema es correcto, ejecutar este 
    # downgrade en producción es peligroso. Si ya hemos guardado IDs de 50 
    # caracteres, revertir la columna a 36 truncará esos datos de forma 
    # irreversible sin lanzar un error (dependiendo de la configuración de Postgres). 
    # En un entorno real, habría que limpiar los datos a mano antes de hacer este rollback.
    op.alter_column(
        "competitors",
        "id_global",
        existing_type=sa.String(length=64),
        type_=sa.String(length=36),
        existing_nullable=False,
    )