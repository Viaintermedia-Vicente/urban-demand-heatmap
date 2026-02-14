import os
from functools import lru_cache

from sqlalchemy import create_engine


@lru_cache(maxsize=1)
def get_engine():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return create_engine(database_url, future=True)
