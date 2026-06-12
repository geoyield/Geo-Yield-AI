-- Open Data BCN datasets (neighborhood-level, much finer than MITMA's 10
-- districts: Barcelona's 73 neighborhoods).
-- Populated by ingestion/load_opendata_bcn.py.

-- Barcelona neighborhoods reference table.
CREATE TABLE IF NOT EXISTS neighborhoods (
    neighborhood_code INTEGER PRIMARY KEY,
    neighborhood_name TEXT NOT NULL,
    district_code INTEGER NOT NULL,
    district_name TEXT NOT NULL
);

-- Ground-floor commercial premises (cens d'activitats comercials):
-- competitor / market-saturation data at street-address granularity.
CREATE TABLE IF NOT EXISTS commercial_premises (
    id TEXT PRIMARY KEY,
    activity_status TEXT,
    sector TEXT,
    activity_group TEXT,
    activity_name TEXT,
    name TEXT,
    address TEXT,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    neighborhood_code INTEGER,
    district_code INTEGER
);

CREATE INDEX IF NOT EXISTS idx_commercial_premises_neighborhood ON commercial_premises (neighborhood_code);
CREATE INDEX IF NOT EXISTS idx_commercial_premises_group ON commercial_premises (activity_group);

-- Population by neighborhood/age/sex (padró municipal, latest snapshot).
CREATE TABLE IF NOT EXISTS population_by_neighborhood (
    reference_date DATE NOT NULL,
    neighborhood_code INTEGER NOT NULL,
    age SMALLINT NOT NULL,
    sex SMALLINT NOT NULL,
    people INTEGER NOT NULL,
    PRIMARY KEY (reference_date, neighborhood_code, age, sex)
);

-- Average disposable household income per capita by neighborhood (RFD).
CREATE TABLE IF NOT EXISTS income_by_neighborhood (
    year INTEGER NOT NULL,
    neighborhood_code INTEGER NOT NULL,
    income_eur_per_capita NUMERIC NOT NULL,
    PRIMARY KEY (year, neighborhood_code)
);
