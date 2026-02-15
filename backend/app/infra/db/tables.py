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
