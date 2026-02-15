from __future__ import annotations

import os

from fastapi import FastAPI
from sqlalchemy import create_engine

from app.api.routers import events, heatmap


def create_app(engine=None) -> FastAPI:
    app = FastAPI(title="Hotspots API", version="0.1.0")
    if engine is None:
        database_url = os.getenv("DATABASE_URL")
        engine = create_engine(database_url, future=True) if database_url else None
    app.state.db_engine = engine

    app.include_router(heatmap.router, prefix="/api")
    app.include_router(events.router, prefix="/api")
    return app


app = create_app()
