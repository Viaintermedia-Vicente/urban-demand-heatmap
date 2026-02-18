#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
  cat <<'USAGE'
Uso: cron_sync_weather.sh [--help]
Variables:
  LAT (default: 40.4168)
  LON (default: -3.7038)
  PAST_DAYS (default: 1)
  FUTURE_DAYS (default: 1)
  LOCATION_NAME (default: Madrid)
  DATABASE_URL (default: sqlite://../tmp_dev.db)
USAGE
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$BACKEND_DIR"

if [[ -d ".venv" ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

DEFAULT_DB_PATH="$(cd "$BACKEND_DIR/.." && pwd)/tmp_dev.db"
export DATABASE_URL="${DATABASE_URL:-sqlite:///${DEFAULT_DB_PATH}}"
LAT="${LAT:-40.4168}"
LON="${LON:--3.7038}"
PAST_DAYS="${PAST_DAYS:-1}"
FUTURE_DAYS="${FUTURE_DAYS:-1}"
LOCATION_NAME="${LOCATION_NAME:-Madrid}"

python -m app.jobs.sync_weather --lat "$LAT" --lon "$LON" --past-days "$PAST_DAYS" --future-days "$FUTURE_DAYS" --location-name "$LOCATION_NAME"
