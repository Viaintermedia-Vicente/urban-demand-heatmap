from __future__ import annotations

import argparse
import os

from app.migrations import add_event_integrity


def migrate(database_url: str | None = None) -> None:
    add_event_integrity.run(database_url=database_url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DB migrations for FinMaster")
    parser.add_argument("--database-url", dest="database_url", default=None)
    args = parser.parse_args()
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL must be provided via --database-url or env")
    migrate(database_url)


if __name__ == "__main__":
    main()
