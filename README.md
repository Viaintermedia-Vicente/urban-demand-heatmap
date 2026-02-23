# Hotspots urbanos: predicción de zonas de alta actividad basada en eventos

## Descripción
Plataforma para equipos de planificación urbana y comercios locales que identifica zonas con alta concentración de actividad a partir de eventos ciudadanos y streams operativos.

## Estado del proyecto
- Docs ✅ (actualizadas a contratos reales)
- Docker ✅ (compose con backend y frontend)
- Backend ✅
- Front ✅
- IA opcional ⚪ (módulos opcionales, no críticos)

## Demo local (Docker Compose)
1. `docker compose build`
2. `docker compose up -d`
3. Acceder a `http://localhost:5174` (frontend) y `http://localhost:8000/docs` (API).
4. Para detener el entorno: `docker compose down`

## Ejecución en local
- **Requisitos**: Docker Desktop (o motor Docker 24+) y Docker Compose v2.
- **Pasos rápidos**:
  1. `git clone <repo-url> tfm-hotspots && cd tfm-hotspots`
  2. `cd docker && docker compose up --build`
- **URLs**:
  - Frontend: `http://localhost:5174`
  - Backend: `http://localhost:8000/docs`

## Arquitectura a alto nivel
- Backend FastAPI centralizado para ingesta, predicción y exposición de API REST.
- Base de datos Postgres como almacén transaccional y para consultas geoespaciales.
- Frontend React para visualización del heatmap y panel de eventos.
- Job de importación y enriquecimiento periódico (ETL liviano o cron job).

## Endpoints principales
- `GET /api/heatmap`: devuelve hotspots y, si hay datos, eventos asociados (o sintéticos si no hay datos).
- `GET /api/events`: lista eventos actuales desde `from_hour`, con coordenadas cuando están disponibles.

## Testing
- Backend: `pytest` con fixtures para Postgres y pruebas de contrato.
- Frontend: pruebas ligeras con herramientas de testing de React (por ejemplo, Vitest + Testing Library).

## Calidad y tests
- Ejecutar todas las pruebas: `make test`
- Sólo unitarias (rápidas): `make test-unit` o `make test-fast`
- Pre-commit: `pip install -r backend/requirements.txt && pip install pre-commit && pre-commit install`
- Verificación manual: `pre-commit run --all-files`
- CI: GitHub Actions (`.github/workflows/ci.yml`) instala dependencias del backend y ejecuta `make test` en cada push/PR.

## CLI
- Ejecutar comandos desde `backend/`: `python -m app.cli.main heatmap --date 2026-02-12 --hour 19`
- Listar eventos (placeholder): `python -m app.cli.main events --date 2026-02-12 --from-hour 18`
- Lanzar import demo: `python -m app.cli.main import --source csv --file datos.csv`
- La CLI reutiliza la lógica del dominio, por lo que refleja los mismos resultados que verán la API y el frontend una vez implementados.

## API FastAPI
- Lanzar la API REST localmente:
  ```
  cd backend
  uvicorn app.api.main:app --reload
  ```
- El servidor utiliza `DATABASE_URL`; asegúrate de que apunte a Postgres o SQLite antes de iniciar.

## Roadmap
1. MVP de predicción con modelos estadísticos simples.
2. Integración de streams en tiempo real (eventos IoT / municipales).
3. Dashboard avanzado con filtros temporales y alertas.
4. Integración opcional de Ollama/RAG para consultas en lenguaje natural sobre datos históricos.

## Licencia y contribución
- Licencia propuesta: MIT (pendiente de confirmación).
- Guía de contribución: PRs vía forks, revisión por pares, convenciones de commit semánticas.

## Dataset y entrenamiento
- Materializar snapshots para una fecha/hora:
  ```bash
  cd backend
  python -m app.jobs.materialize_snapshots materialize --date 2026-03-01 --hour 22 --lat 40.4168 --lon -3.7038
  ```
- Exportar dataset para entrenamiento:
  ```bash
  cd backend
  python -m app.jobs.export_training_dataset --out ../dataset.csv --start-date 2026-03-01 --end-date 2026-03-07
  ```
- Entrenar baseline lineal con las snapshots exportadas:
  ```bash
  cd backend
  python -m app.jobs.train_baseline --csv-path ../dataset.csv --model-out ../model.json
  ```

### Quick check
- `cd backend && scripts/quick_check.sh` (genera datos, dataset y modelo, dejando el log en `run_logs/last_run.log`).


### Sync de eventos y meteorología
- **Jobs individuales** (desde `backend/`):
  - `python -m app.jobs.sync_weather --lat 40.4168 --lon -3.7038 --past-days 1 --future-days 2 --location-name Madrid`
  - `python -m app.jobs.sync_events --city Madrid --past-days 7 --future-days 7`
- **Providers**:
  - Meteo: por defecto usa un dataset demo offline. Para consumir Open-Meteo en vivo exporta `SYNC_WEATHER_PROVIDER=open-meteo` (no requiere API key).
  - Eventos: define `TICKETMASTER_API_KEY=<tu_api_key>` para activar el provider real. Si no existe, se usa el generador demo/backfill.
- **Backfill / histórico**: los flags `--past-days` y `--future-days` existen en ambos jobs para rellenar histórico y pronóstico sin duplicar datos (upsert idempotente por `source + external_id` y `source + lat+lon + observed_at`).
- **Scripts cron-safe**: `backend/scripts/cron_sync_weather.sh` y `backend/scripts/cron_sync_events.sh` encapsulan la activación del entorno, `DATABASE_URL` (por defecto `../tmp_dev.db`) y parámetros básicos. Añádelos a tu cron/planificador (Plesk) invocando `bash backend/scripts/cron_sync_*.sh`.
- **Plesk / Docker**: en contenedores puedes ejecutar `docker compose exec backend bash scripts/cron_sync_weather.sh` y lo mismo para eventos. Configura las variables de entorno (`DATABASE_URL`, `TICKETMASTER_API_KEY`, etc.) en el servicio antes de ejecutar.
- **Inflador demo**: `docker compose exec backend python -m app.jobs.inflate_demo_data --city Madrid --lat 40.4168 --lon -3.7038 --past-days 90 --future-days 30 --per-day 20` genera eventos, meteo, snapshots y dataset/modelos para demos.

### Run pipeline (copy/paste safe)
```bash
: "# Activate virtualenv"
source backend/.venv/bin/activate
: "# Move into backend"
cd backend
: "# Set database location (defaults to sqlite file)"
: "# Set database location (defaults to sqlite file in repo)"
export DATABASE_URL="sqlite:///${PWD}/tmp_dev.db"
: "# Reset SQLite database"
rm -f "${PWD}/tmp_dev.db"
: "# Import events/venues/rules from CSV seeds"
python -m app.jobs.import_csv ../data
: "# Attempt to import weather from Open-Meteo (may fail offline)"
python -m app.jobs.import_weather --lat 40.4168 --lon -3.7038 --start-date 2026-03-01 --end-date 2026-03-02 --location-name Madrid
: "# Materialize feature snapshots for a sample target"
python -m app.jobs.materialize_snapshots materialize --date 2026-03-01 --hour 22 --lat 40.4168 --lon -3.7038
: "# Export dataset to CSV"
python -m app.jobs.export_training_dataset --out ../dataset.csv --start-date 2026-03-01 --end-date 2026-03-07
: "# Train baseline regression and store model"
python -m app.jobs.train_baseline --csv-path ../dataset.csv --model-out ../model.json
: "# Optional sanity checks"
head -n 2 ../dataset.csv
python - <<'EOF'
import os
from sqlalchemy import create_engine, text
e=create_engine(os.environ["DATABASE_URL"])
with e.connect() as c:
    print([r[1] for r in c.execute(text("PRAGMA table_info(event_feature_snapshots)")).fetchall()])
EOF
make test
```

## Despliegue Docker / Plesk

1. Arranca los servicios:
   ```bash
   cd docker
   docker compose up -d
   ```
2. Inicializa la base de datos (crea tablas y carga semillas). Hay un script incluido:
   ```bash
   cd docker
   ./init_db.sh
   ```
   El script:
   - crea el esquema con SQLAlchemy (`metadata.create_all`)
   - aplica migración defensiva (`python -m app.jobs.migrate_db`)
   - importa seeds (`python -m app.jobs.import_csv`, usando `data/`)
3. Verifica rápidamente:
   ```bash
   docker compose exec db psql -U hotspots_user -d hotspots -c "\\dt"
   docker compose exec backend curl -s "http://localhost:8000/api/heatmap?date=2026-02-23&hour=20&lat=40.4168&lon=-3.7038" | head
   ```
