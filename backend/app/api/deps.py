from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.engine import Engine


def get_engine(request: Request) -> Engine:
    engine = getattr(request.app.state, "db_engine", None)
    if engine is None:
        raise HTTPException(status_code=500, detail="Database engine not configured")
    return engine
