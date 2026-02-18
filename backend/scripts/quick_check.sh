#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

if [[ ! -d .venv ]]; then
    echo ".venv not found. Please create the virtualenv first." >&2
    exit 1
fi

source .venv/bin/activate

DEFAULT_SQLITE="sqlite:////Users/vicente/Trabajos/VTC/proyecto/FinMaster/tmp_dev.db"
DB_URL="${DATABASE_URL:-$DEFAULT_SQLITE}"
export DATABASE_URL="$DB_URL"

LOG_DIR="../run_logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/last_run.log"

exec 3>&1
exec >"$LOG_FILE" 2>&1

sqlite_path=$(python - <<'PY'
import os
from urllib.parse import urlparse
url = os.environ["DATABASE_URL"]
if not url.startswith("sqlite"):
    print("")
else:
    parsed = urlparse(url)
    path = parsed.path
    if parsed.netloc:
        path = "//" + parsed.netloc + path
    print(path)
PY
)

if [[ -n "$sqlite_path" ]]; then
    rm -f "$sqlite_path"
fi

python -m app.jobs.import_csv ../data

if ! python -m app.jobs.import_weather --lat 40.4168 --lon -3.7038 --start-date 2026-03-01 --end-date 2026-03-02 --location-name Madrid; then
    python - <<'PY'
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
engine = create_engine(os.environ["DATABASE_URL"])
observed_at = datetime(2026, 3, 1, 22, tzinfo=timezone.utc)
with engine.begin() as conn:
    conn.execute(text("DELETE FROM weather_observations WHERE lat=:lat AND lon=:lon AND observed_at=:obs"),
                 {"lat": 40.4168, "lon": -3.7038, "obs": observed_at})
    conn.execute(text("""
        INSERT INTO weather_observations (
            source, location_name, lat, lon, observed_at,
            temperature_c, precipitation_mm, rain_mm, snowfall_mm,
            cloud_cover_pct, wind_speed_kmh, wind_gust_kmh, wind_dir_deg,
            humidity_pct, pressure_hpa, visibility_m, weather_code,
            created_at, updated_at
        ) VALUES (
            :source, :location, :lat, :lon, :obs,
            :temp, :precip, :rain, :snow,
            :clouds, :wind, :gust, :dir,
            :hum, :pressure, :visibility, :code,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
    """), {
        "source": "manual",
        "location": "Madrid",
        "lat": 40.4168,
        "lon": -3.7038,
        "obs": observed_at,
        "temp": 20.0,
        "precip": 0.1,
        "rain": 0.1,
        "snow": 0.0,
        "clouds": 35.0,
        "wind": 10.0,
        "gust": 16.0,
        "dir": 95.0,
        "hum": 50.0,
        "pressure": 1011.0,
        "visibility": 9000.0,
        "code": 3,
    })
PY
fi

python -m app.jobs.materialize_snapshots materialize --date 2026-03-01 --hour 22 --lat 40.4168 --lon -3.7038
python -m app.jobs.export_training_dataset --out ../dataset.csv --start-date 2026-03-01 --end-date 2026-03-07
python -m app.jobs.train_baseline --csv-path ../dataset.csv --model-out ../model.json

counts=$(python - <<'PY'
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as conn:
    events = conn.execute(text("SELECT COUNT(*) FROM events")).scalar_one()
    venues = conn.execute(text("SELECT COUNT(*) FROM venues")).scalar_one()
    weather = conn.execute(text("SELECT COUNT(*) FROM weather_observations")).scalar_one()
    snapshots = conn.execute(text("SELECT COUNT(*) FROM event_feature_snapshots")).scalar_one()
print(f"events={events} venues={venues} weather={weather} snapshots={snapshots}")
PY
)

sample_line=$(tail -n +2 ../dataset.csv | head -n 1 || true)
visibility_status=$(python - <<'PY'
import csv
from pathlib import Path
with Path("../dataset.csv").open() as fp:
    reader = csv.DictReader(fp)
    row = next(reader, None)
if not row:
    print("FAIL (no data)")
else:
    val = (row.get("visibility_m") or "").strip()
    if val:
        print(f"OK ({val})")
    else:
        print("FAIL (empty)")
PY
)

summary=()
summary+=("DB: ${DATABASE_URL}")
summary+=("Counts: ${counts}")
summary+=("Sample: ${sample_line:-<no data>}")
summary+=("Visibility: ${visibility_status}")
summary+=("Dataset: ../dataset.csv")
summary+=("Model/Log: ../model.json | ${LOG_FILE}")

exec 1>&3 3>&-

printf '%s\n' "${summary[@]}"
