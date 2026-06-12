-- OpenStreetMap points of interest (cafes, bars, restaurants, fast food,
-- pubs) within Barcelona, for competitor / amenity density analysis.
-- Populated by ingestion/load_osm_pois.py.

CREATE TABLE IF NOT EXISTS osm_pois (
    osm_type TEXT NOT NULL,
    osm_id BIGINT NOT NULL,
    category TEXT NOT NULL,
    name TEXT,
    cuisine TEXT,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (osm_type, osm_id)
);

CREATE INDEX IF NOT EXISTS idx_osm_pois_category ON osm_pois (category);
