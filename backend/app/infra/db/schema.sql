CREATE TABLE IF NOT EXISTS venues (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT,
    name TEXT NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    city TEXT NOT NULL,
    region TEXT,
    country TEXT NOT NULL,
    address_line1 TEXT,
    address_line2 TEXT,
    postal_code TEXT,
    max_capacity INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (source, external_id) WHERE external_id IS NOT NULL
);

CREATE TABLE IF NOT EXISTS category_rules (
    category TEXT PRIMARY KEY,
    fill_factor DOUBLE PRECISION NOT NULL CHECK (fill_factor >= 0 AND fill_factor <= 1),
    fallback_attendance INTEGER NOT NULL CHECK (fallback_attendance >= 0),
    default_duration_min INTEGER NOT NULL CHECK (default_duration_min > 0),
    pre_event_min INTEGER NOT NULL CHECK (pre_event_min >= 0),
    post_event_min INTEGER NOT NULL CHECK (post_event_min >= 0),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    start_dt TIMESTAMPTZ NOT NULL,
    end_dt TIMESTAMPTZ NOT NULL,
    timezone TEXT NOT NULL,
    venue_id INTEGER REFERENCES venues (id),
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    status TEXT,
    url TEXT,
    expected_attendance INTEGER,
    popularity_score DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN NOT NULL DEFAULT true,
    UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_events_start_dt ON events (start_dt);
CREATE INDEX IF NOT EXISTS idx_events_category ON events (category);
CREATE INDEX IF NOT EXISTS idx_venues_city ON venues (city);
CREATE INDEX IF NOT EXISTS idx_venues_name ON venues (name);

CREATE TABLE IF NOT EXISTS weather_observations (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    location_name TEXT,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    temperature_c DOUBLE PRECISION,
    precipitation_mm DOUBLE PRECISION,
    rain_mm DOUBLE PRECISION,
    snowfall_mm DOUBLE PRECISION,
    cloud_cover_pct DOUBLE PRECISION,
    wind_speed_kmh DOUBLE PRECISION,
    wind_gust_kmh DOUBLE PRECISION,
    wind_dir_deg DOUBLE PRECISION,
    humidity_pct DOUBLE PRECISION,
    pressure_hpa DOUBLE PRECISION,
    visibility_m DOUBLE PRECISION,
    weather_code INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (source, lat, lon, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_weather_observed_at ON weather_observations (observed_at);

CREATE TABLE IF NOT EXISTS event_feature_snapshots (
    id SERIAL PRIMARY KEY,
    target_at TIMESTAMPTZ NOT NULL,
    event_id TEXT NOT NULL,
    event_start_dt TIMESTAMPTZ NOT NULL,
    event_end_dt TIMESTAMPTZ,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    category TEXT,
    expected_attendance INTEGER,
    hours_to_start DOUBLE PRECISION,
    weekday INTEGER,
    month INTEGER,
    temperature_c DOUBLE PRECISION,
    precipitation_mm DOUBLE PRECISION,
    rain_mm DOUBLE PRECISION,
    snowfall_mm DOUBLE PRECISION,
    wind_speed_kmh DOUBLE PRECISION,
    wind_gust_kmh DOUBLE PRECISION,
    weather_code INTEGER,
    humidity_pct DOUBLE PRECISION,
    pressure_hpa DOUBLE PRECISION,
    cloud_cover_pct DOUBLE PRECISION,
    score_base DOUBLE PRECISION,
    score_weather_factor DOUBLE PRECISION,
    score_final DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (target_at, event_id)
);

CREATE INDEX IF NOT EXISTS idx_event_snapshots_target ON event_feature_snapshots (target_at);
CREATE INDEX IF NOT EXISTS idx_event_snapshots_event ON event_feature_snapshots (event_id);

