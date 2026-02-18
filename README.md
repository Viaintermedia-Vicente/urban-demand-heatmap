# Hotspots urbanos: predicción de zonas de alta actividad basada en eventos

## Descripción
Plataforma para equipos de planificación urbana y comercios locales que identifica zonas con alta concentración de actividad a partir de eventos ciudadanos y streams operativos.

## Estado del proyecto
- Docs ✅
- Docker ⏳
- Backend ⏳
- Front ⏳
- IA opcional ⏳

## Demo local (Docker Compose)
1. `docker compose build`
2. `docker compose up -d`
3. Acceder a `http://localhost:3000` para el front y `http://localhost:8000/docs` para la API.
4. Para detener el entorno: `docker compose down`

> Nota: Los servicios aún no existen; esta guía se actualizará cuando se añadan los contenedores.

## Ejecución en local
- **Requisitos**: Docker Desktop (o motor Docker 24+) y Docker Compose v2.
- **Pasos rápidos**:
  1. `git clone <repo-url> tfm-hotspots && cd tfm-hotspots`
  2. `cd docker && docker compose up --build`
- **URLs**:
  - Frontend: `http://localhost:5173`
  - Backend: `http://localhost:8000/health` y `http://localhost:8000/docs`
- Nota: en esta fase sólo existe la infraestructura base; los servicios reales se irán completando durante el desarrollo del TFM.

## Arquitectura a alto nivel
- Backend FastAPI centralizado para ingesta, predicción y exposición de API REST.
- Base de datos Postgres como almacén transaccional y para consultas geoespaciales.
- Frontend React para visualización del heatmap y panel de eventos.
- Job de importación y enriquecimiento periódico (ETL liviano o cron job).

## Endpoints esperados
- `GET /heatmap`: devuelve celdas geoespaciales con score y metadata.
- `GET /events`: lista eventos recientes y filtros por categoría, horario y ubicación.

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

### Run pipeline (copy/paste safe)
```bash
: "# Activate virtualenv"
source backend/.venv/bin/activate
: "# Move into backend"
cd backend
: "# Set database location (defaults to sqlite file)"
export DATABASE_URL="sqlite:////Users/vicente/Trabajos/VTC/proyecto/FinMaster/tmp_dev.db"
: "# Reset SQLite database"
rm -f /Users/vicente/Trabajos/VTC/proyecto/FinMaster/tmp_dev.db
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
