-- MITMA mobility data (Barcelona) schema.
-- Populated by ingestion/load_mitma_data.py.

CREATE TABLE IF NOT EXISTS zones (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_barcelona BOOLEAN NOT NULL DEFAULT FALSE
);

-- Origin/destination trip flows per hour, filtered to rows touching a
-- Barcelona district (as origin and/or destination). The zone on the other
-- end of the trip may be outside Spain's "distritos" zonification (e.g. a
-- foreign NUTS3 region such as FR101), so these are not FK-constrained to
-- `zones`.
CREATE TABLE IF NOT EXISTS mobility_flows_hourly (
    date DATE NOT NULL,
    hour SMALLINT NOT NULL CHECK (hour BETWEEN 0 AND 23),
    origin_zone_id TEXT NOT NULL,
    destination_zone_id TEXT NOT NULL,
    trips NUMERIC NOT NULL,
    trips_km NUMERIC NOT NULL,
    PRIMARY KEY (date, hour, origin_zone_id, destination_zone_id)
);

CREATE INDEX IF NOT EXISTS idx_mobility_flows_origin ON mobility_flows_hourly (origin_zone_id);
CREATE INDEX IF NOT EXISTS idx_mobility_flows_destination ON mobility_flows_hourly (destination_zone_id);

-- Daily resident/overnight-stay population per Barcelona district.
CREATE TABLE IF NOT EXISTS zone_population_daily (
    date DATE NOT NULL,
    zone_id TEXT NOT NULL,
    people NUMERIC NOT NULL,
    PRIMARY KEY (date, zone_id)
);

-- Tracks which raw daily files have already been loaded, for idempotent reruns.
CREATE TABLE IF NOT EXISTS ingestion_state (
    dataset TEXT NOT NULL,
    file_date DATE NOT NULL,
    row_count INTEGER NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset, file_date)
);
