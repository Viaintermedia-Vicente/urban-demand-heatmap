#!/usr/bin/env bash
set -euo pipefail

# Inicializa el esquema y siembra datos de ejemplo en el contenedor Docker.
# Requisitos: docker compose up -d (servicios db y backend levantados).

cd "$(dirname "$0")"

echo "👉 Creando tablas con SQLAlchemy metadata..."
docker compose exec backend python - <<'PY'
import os
from sqlalchemy import create_engine
from app.infra.db.tables import metadata

engine = create_engine(os.environ["DATABASE_URL"], future=True)
metadata.create_all(engine)
print("✔ Tablas creadas")
PY

echo "👉 Aplicando migración defensiva..."
docker compose exec backend python -m app.jobs.migrate_db

echo "👉 Importando datos semilla (venues, events, category_rules)..."
docker compose exec backend python -m app.jobs.import_csv

echo "✅ Base de datos lista."
