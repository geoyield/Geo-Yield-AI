"""
==============================================================================
PLANTILLA BASE DE MIGRACIONES (ALEMBIC / MAKO)
==============================================================================
Este archivo sirve como molde inmutable para la generación automática de
scripts de migración. Al ejecutar 'alembic revision', el motor de plantillas
Mako inyecta los metadatos (revision_id, timestamps y código autogenerado)
en las variables marcadas con ${...}.

No modificar la estructura de este archivo a menos que se requiera alterar
el comportamiento global de todas las migraciones futuras del proyecto.
"""
"""${message}

# ----------------------------------------------------------------------------
# METADATOS DE ENRUTAMIENTO (Árbol de migraciones)
# ----------------------------------------------------------------------------
Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}

# ----------------------------------------------------------------------------
# OPERACIONES DE CAMBIO DE ESQUEMA (Forward & Backward)
# ----------------------------------------------------------------------------
def upgrade() -> None:
    """Aplica los cambios en el esquema hacia adelante."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Revierte los cambios en el esquema hacia atrás (Rollback)."""
    ${downgrades if downgrades else "pass"}
