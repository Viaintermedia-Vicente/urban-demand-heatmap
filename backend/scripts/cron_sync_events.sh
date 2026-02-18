#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
  cat <<'USAGE'
Uso: cron_sync_events.sh [--help]
Variables soportadas:
  CITY (default: Madrid)
  PAST_DAYS (default: 1)
  FUTURE_DAYS (default: 3)
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
CITY="${CITY:-Madrid}"
PAST_DAYS="${PAST_DAYS:-1}"
FUTURE_DAYS="${FUTURE_DAYS:-3}"

python -m app.jobs.sync_events --city "$CITY" --past-days "$PAST_DAYS" --future-days "$FUTURE_DAYS"
