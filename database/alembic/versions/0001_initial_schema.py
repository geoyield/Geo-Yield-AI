"""
==============================================================================
MIGRACIÓN 0001: ESQUEMA INICIAL (FASE 1)
==============================================================================
Revision ID: 0001
Revises:
Create Date: 2026-08-08

Esta es la migración principal que crea la base de datos desde cero.
Contiene las tablas relacionales para los distritos, la tabla espacial para los 
negocios (PostGIS), y la vista SQL que calcula la oportunidad de negocio.

Aprendizaje clave sobre el 'Opportunity Score':
Decidimos implementarlo como una VISTA SQL (`district_scorecard`) en lugar de 
una columna fija en una tabla. Esto resuelve un gran problema: si mañana 
cargamos nuevos datos de tráfico peatonal, la vista siempre calculará el score 
correcto al vuelo, evitando el riesgo de que una columna física quede desactualizada.

"""

from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ----------------------------------------------------------------------------
# DDL: VISTA ANALÍTICA (CÁLCULO DEL SCORE)
# ----------------------------------------------------------------------------
DISTRICT_SCORECARD_VIEW = """
CREATE OR REPLACE VIEW district_scorecard AS
WITH competitor_counts AS (
    SELECT codi_districte, COUNT(*)::numeric AS total_competitors
    FROM competitors
    GROUP BY codi_districte
),
combined AS (
    SELECT
        d.codi_districte,
        d.nom_districte,
        dm.daily_foot_traffic,
        di.renta_media,
        COALESCE(cc.total_competitors, 0) AS total_competitors
    FROM districts d
    JOIN district_mobility dm ON dm.codi_districte = d.codi_districte
    JOIN district_income di ON di.codi_districte = d.codi_districte
    LEFT JOIN competitor_counts cc ON cc.codi_districte = d.codi_districte
),
bounds AS (
    SELECT
        MIN(daily_foot_traffic) AS min_traffic, MAX(daily_foot_traffic) AS max_traffic,
        MIN(renta_media) AS min_income, MAX(renta_media) AS max_income,
        MIN(total_competitors) AS min_comp, MAX(total_competitors) AS max_comp
    FROM combined
)
SELECT
    c.codi_districte,
    c.nom_districte,
    c.daily_foot_traffic,
    c.renta_media,
    c.total_competitors,
    ROUND(
        (
            COALESCE((c.daily_foot_traffic - b.min_traffic) / NULLIF(b.max_traffic - b.min_traffic, 0), 0) * 0.40
            + COALESCE((c.renta_media - b.min_income) / NULLIF(b.max_income - b.min_income, 0), 0) * 0.40
            + (1 - COALESCE((c.total_competitors - b.min_comp) / NULLIF(b.max_comp - b.min_comp, 0), 0)) * 0.20
        ) * 100
    , 2) AS opportunity_score
FROM combined c
CROSS JOIN bounds b
ORDER BY opportunity_score DESC;
"""


def upgrade() -> None:
    # Aseguramos que PostGIS está activo ANTES de intentar crear las tablas espaciales.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "districts",
        sa.Column("codi_districte", sa.SmallInteger(), nullable=False),
        sa.Column("nom_districte", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("codi_districte"),
    )
    op.create_table(
        "district_income",
        sa.Column("codi_districte", sa.SmallInteger(), nullable=False),
        sa.Column("renta_media", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("periodo", sa.SmallInteger(), nullable=True),
        sa.Column("loaded_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["codi_districte"], ["districts.codi_districte"]),
        sa.PrimaryKeyConstraint("codi_districte"),
    )
    op.create_table(
        "district_mobility",
        sa.Column("codi_districte", sa.SmallInteger(), nullable=False),
        sa.Column("daily_foot_traffic", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=True),
        sa.Column("loaded_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["codi_districte"], ["districts.codi_districte"]),
        sa.PrimaryKeyConstraint("codi_districte"),
    )
    op.create_table(
        "neighborhoods",
        sa.Column("codi_barri", sa.SmallInteger(), nullable=False),
        sa.Column("nom_barri", sa.String(length=100), nullable=False),
        sa.Column("codi_districte", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(["codi_districte"], ["districts.codi_districte"]),
        sa.PrimaryKeyConstraint("codi_barri"),
    )
    op.create_index(
        op.f("ix_neighborhoods_codi_districte"), "neighborhoods", ["codi_districte"], unique=False
    )
    op.create_table(
        "competitors",
        sa.Column("id_global", sa.String(length=36), nullable=False),
        sa.Column("nom_local", sa.String(length=255), nullable=True),
        sa.Column("nom_activitat", sa.String(length=255), nullable=False),
        sa.Column("nom_grup_activitat", sa.String(length=255), nullable=True),
        sa.Column("nom_sector_activitat", sa.String(length=255), nullable=True),
        sa.Column("codi_barri", sa.SmallInteger(), nullable=True),
        sa.Column("codi_districte", sa.SmallInteger(), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geography(
                geometry_type="POINT", srid=4326, dimension=2, from_text="ST_GeogFromText", name="geography"
            ),
            nullable=False,
        ),
        sa.Column("loaded_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["codi_barri"], ["neighborhoods.codi_barri"]),
        sa.ForeignKeyConstraint(["codi_districte"], ["districts.codi_districte"]),
        sa.PrimaryKeyConstraint("id_global"),
    )

    # Nota de desarrollo: No creamos el índice espacial de PostGIS aquí de forma manual.
    # La librería GeoAlchemy2 lo crea por detrás automáticamente. Si lo pusiera aquí, 
    # la migración fallaría por intentar crearlo dos veces.
    op.create_index(op.f("ix_competitors_codi_barri"), "competitors", ["codi_barri"], unique=False)
    op.create_index(op.f("ix_competitors_codi_districte"), "competitors", ["codi_districte"], unique=False)

    op.execute(DISTRICT_SCORECARD_VIEW)


def downgrade() -> None:
    # Este bloque deshace todo lo creado arriba.
    op.execute("DROP VIEW IF EXISTS district_scorecard")

    op.drop_index(op.f("ix_competitors_codi_districte"), table_name="competitors")
    op.drop_index(op.f("ix_competitors_codi_barri"), table_name="competitors")

    op.drop_table("competitors")
    op.drop_index(op.f("ix_neighborhoods_codi_districte"), table_name="neighborhoods")
    op.drop_table("neighborhoods")
    op.drop_table("district_mobility")
    op.drop_table("district_income")
    op.drop_table("districts")
