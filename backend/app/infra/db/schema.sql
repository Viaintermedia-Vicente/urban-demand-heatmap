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
    UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_events_start_dt ON events (start_dt);
CREATE INDEX IF NOT EXISTS idx_events_category ON events (category);
CREATE INDEX IF NOT EXISTS idx_venues_city ON venues (city);
CREATE INDEX IF NOT EXISTS idx_venues_name ON venues (name);
