from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, MetaData, Table, Text

metadata = MetaData()

venues_table = Table(
    "venues",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("source", Text, nullable=False),
    Column("external_id", Text),
    Column("name", Text, nullable=False),
    Column("lat", Float, nullable=False),
    Column("lon", Float, nullable=False),
    Column("city", Text, nullable=False),
    Column("region", Text),
    Column("country", Text, nullable=False),
    Column("address_line1", Text),
    Column("address_line2", Text),
    Column("postal_code", Text),
    Column("max_capacity", Integer),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)

category_rules_table = Table(
    "category_rules",
    metadata,
    Column("category", Text, primary_key=True),
    Column("fill_factor", Float, nullable=False),
    Column("fallback_attendance", Integer, nullable=False),
    Column("default_duration_min", Integer, nullable=False),
    Column("pre_event_min", Integer, nullable=False),
    Column("post_event_min", Integer, nullable=False),
    Column("updated_at", DateTime(timezone=True)),
)

events_table = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("source", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("category", Text, nullable=False),
    Column("subcategory", Text),
    Column("start_dt", DateTime(timezone=True), nullable=False),
    Column("end_dt", DateTime(timezone=True), nullable=False),
    Column("timezone", Text, nullable=False),
    Column("venue_id", Integer, ForeignKey("venues.id")),
    Column("lat", Float, nullable=False),
    Column("lon", Float, nullable=False),
    Column("status", Text),
    Column("url", Text),
    Column("expected_attendance", Integer),
    Column("popularity_score", Float),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)


weather_observations_table = Table(
    "weather_observations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("source", Text, nullable=False),
    Column("location_name", Text),
    Column("lat", Float, nullable=False),
    Column("lon", Float, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("temperature_c", Float),
    Column("precipitation_mm", Float),
    Column("rain_mm", Float),
    Column("snowfall_mm", Float),
    Column("cloud_cover_pct", Float),
    Column("wind_speed_kmh", Float),
    Column("wind_gust_kmh", Float),
    Column("wind_dir_deg", Float),
    Column("humidity_pct", Float),
    Column("pressure_hpa", Float),
    Column("visibility_m", Float),
    Column("weather_code", Integer),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)



event_feature_snapshots_table = Table(
    "event_feature_snapshots",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("target_at", DateTime(timezone=True), nullable=False),
    Column("event_id", Text, nullable=False),
    Column("event_start_dt", DateTime(timezone=True), nullable=False),
    Column("event_end_dt", DateTime(timezone=True)),
    Column("lat", Float, nullable=False),
    Column("lon", Float, nullable=False),
    Column("category", Text),
    Column("expected_attendance", Integer),
    Column("hours_to_start", Float),
    Column("weekday", Integer),
    Column("month", Integer),
    Column("temperature_c", Float),
    Column("precipitation_mm", Float),
    Column("rain_mm", Float),
    Column("snowfall_mm", Float),
    Column("wind_speed_kmh", Float),
    Column("wind_gust_kmh", Float),
    Column("weather_code", Integer),
    Column("humidity_pct", Float),
    Column("pressure_hpa", Float),
    Column("visibility_m", Float),
    Column("cloud_cover_pct", Float),
    Column("score_base", Float),
    Column("score_weather_factor", Float),
    Column("score_final", Float),
    Column("created_at", DateTime(timezone=True)),
)

