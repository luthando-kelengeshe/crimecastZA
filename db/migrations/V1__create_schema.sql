-- V1__create_schema.sql
-- Full 3NF schema for CrimecastZA (PostgreSQL + PostGIS)
-- Idempotent: all CREATE statements use IF NOT EXISTS

-- Enable PostGIS extension if not already present
CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------------------
-- province
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS province (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------------
-- police_station
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS police_station (
    id             SERIAL PRIMARY KEY,
    canonical_name VARCHAR(200) NOT NULL,
    original_name  VARCHAR(200) NOT NULL,
    province_id    INTEGER NOT NULL REFERENCES province(id),
    location       GEOMETRY(Point, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_station_province ON police_station(province_id);
CREATE INDEX IF NOT EXISTS idx_station_location ON police_station USING GIST(location);

-- ---------------------------------------------------------------------------
-- crime_category
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS crime_category (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------------
-- monthly_crime_record
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS monthly_crime_record (
    id            SERIAL PRIMARY KEY,
    station_id    INTEGER NOT NULL REFERENCES police_station(id),
    category_id   INTEGER NOT NULL REFERENCES crime_category(id),
    year          SMALLINT NOT NULL,
    month         SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
    monthly_count INTEGER NOT NULL CHECK (monthly_count >= 0),
    UNIQUE (station_id, category_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_crime_record_station  ON monthly_crime_record(station_id);
CREATE INDEX IF NOT EXISTS idx_crime_record_category ON monthly_crime_record(category_id);
CREATE INDEX IF NOT EXISTS idx_crime_record_period   ON monthly_crime_record(year, month);

-- ---------------------------------------------------------------------------
-- unemployment_record
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS unemployment_record (
    id          SERIAL PRIMARY KEY,
    province_id INTEGER NOT NULL REFERENCES province(id),
    year        SMALLINT NOT NULL,
    quarter     SMALLINT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    rate        NUMERIC(5,2) NOT NULL,
    UNIQUE (province_id, year, quarter)
);

-- ---------------------------------------------------------------------------
-- weather_record
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weather_record (
    id              SERIAL PRIMARY KEY,
    station_id      INTEGER NOT NULL REFERENCES police_station(id),
    year            SMALLINT NOT NULL,
    month           SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
    mean_temp_c     NUMERIC(5,2),
    total_precip_mm NUMERIC(7,2),
    UNIQUE (station_id, year, month)
);

-- ---------------------------------------------------------------------------
-- calendar_event
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS calendar_event (
    id         SERIAL PRIMARY KEY,
    event_date DATE NOT NULL UNIQUE,
    event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('public_holiday', 'payday')),
    is_flagged BOOLEAN NOT NULL DEFAULT TRUE
);

-- ---------------------------------------------------------------------------
-- feature_vector
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feature_vector (
    id                   SERIAL PRIMARY KEY,
    station_id           INTEGER NOT NULL REFERENCES police_station(id),
    category_id          INTEGER NOT NULL REFERENCES crime_category(id),
    year                 SMALLINT NOT NULL,
    month                SMALLINT NOT NULL,
    lag_1                INTEGER,
    lag_2                INTEGER,
    lag_3                INTEGER,
    lag_4                INTEGER,
    lag_5                INTEGER,
    lag_6                INTEGER,
    lag_7                INTEGER,
    lag_8                INTEGER,
    lag_9                INTEGER,
    lag_10               INTEGER,
    lag_11               INTEGER,
    lag_12               INTEGER,
    unemployment_rate    NUMERIC(5,2),
    mean_temp_c          NUMERIC(5,2),
    total_precip_mm      NUMERIC(7,2),
    public_holiday_count SMALLINT,
    payday_count         SMALLINT,
    month_of_year        SMALLINT,
    UNIQUE (station_id, category_id, year, month)
);

-- ---------------------------------------------------------------------------
-- forecast
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS forecast (
    id              SERIAL PRIMARY KEY,
    station_id      INTEGER NOT NULL REFERENCES police_station(id),
    category_id     INTEGER NOT NULL REFERENCES crime_category(id),
    forecast_year   SMALLINT NOT NULL,
    forecast_month  SMALLINT NOT NULL CHECK (forecast_month BETWEEN 1 AND 12),
    predicted_count NUMERIC(10,2) NOT NULL,
    risk_score      SMALLINT NOT NULL CHECK (risk_score BETWEEN 1 AND 5),
    model_version   VARCHAR(100) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (station_id, category_id, forecast_year, forecast_month, model_version)
);

CREATE INDEX IF NOT EXISTS idx_forecast_station  ON forecast(station_id);
CREATE INDEX IF NOT EXISTS idx_forecast_category ON forecast(category_id);
CREATE INDEX IF NOT EXISTS idx_forecast_period   ON forecast(forecast_year, forecast_month);

-- ---------------------------------------------------------------------------
-- pipeline_run_log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_run_log (
    id                SERIAL PRIMARY KEY,
    run_start         TIMESTAMPTZ NOT NULL,
    run_end           TIMESTAMPTZ,
    status            VARCHAR(20) NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    records_processed INTEGER,
    records_skipped   INTEGER,
    mape_per_category JSONB,
    error_message     TEXT
);
