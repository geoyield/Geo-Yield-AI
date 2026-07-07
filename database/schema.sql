-- Schema for the Open Data BCN business census ("Cens de locals i activitat economica").
-- Idempotent: safe to run on every ingestion run and on a fresh volume alike.
-- Source: https://opendata-ajuntament.barcelona.cat/data/dataset/cens-locals-planta-baixa-act-economica

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS business_census (
    id_global               TEXT PRIMARY KEY,
    id_bcn_2016             TEXT,

    codi_principal_activitat INTEGER,
    nom_principal_activitat  TEXT,
    codi_sector_activitat    INTEGER,
    nom_sector_activitat     TEXT,
    codi_grup_activitat      INTEGER,
    nom_grup_activitat       TEXT,
    codi_activitat_2022      INTEGER,
    nom_activitat            TEXT,
    codi_activitat_2016      INTEGER,
    nom_local                TEXT,

    sn_oci_nocturn          BOOLEAN,
    sn_coworking            BOOLEAN,
    sn_servei_degustacio    BOOLEAN,
    sn_obert24h             BOOLEAN,
    sn_mixtura              BOOLEAN,
    sn_carrer               BOOLEAN,
    sn_mercat               BOOLEAN,
    nom_mercat              TEXT,
    sn_galeria              BOOLEAN,
    nom_galeria             TEXT,
    sn_ccomercial           BOOLEAN,
    nom_ccomercial          TEXT,
    sn_eix                  BOOLEAN,
    nom_eix                 TEXT,

    x_utm_etrs89            DOUBLE PRECISION,
    y_utm_etrs89            DOUBLE PRECISION,
    latitud                 DOUBLE PRECISION,
    longitud                DOUBLE PRECISION,
    geom                    geometry(Point, 4326),

    direccio_unica          TEXT,
    codi_via                TEXT,
    nom_via                 TEXT,
    planta                  TEXT,
    porta                   TEXT,
    num_policia_inicial     TEXT,
    lletra_inicial          TEXT,
    num_policia_final       TEXT,
    lletra_final            TEXT,

    solar                   TEXT,
    codi_parcela            TEXT,
    codi_illa               TEXT,
    seccio_censal           TEXT,
    codi_barri              INTEGER,
    nom_barri               TEXT,
    codi_districte          INTEGER,
    nom_districte           TEXT,
    referencia_cadastral    TEXT,

    data_revisio            DATE,
    ingested_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_business_census_districte ON business_census (codi_districte);
CREATE INDEX IF NOT EXISTS ix_business_census_barri ON business_census (codi_barri);
CREATE INDEX IF NOT EXISTS ix_business_census_activitat ON business_census (nom_activitat);
CREATE INDEX IF NOT EXISTS ix_business_census_geom ON business_census USING GIST (geom);
