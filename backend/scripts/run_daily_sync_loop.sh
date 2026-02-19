#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --start YYYY-MM-DD --days N --past N --future N --city CITY --lat LAT --lon LON [--materialize]" >&2
  exit 1
}

START=""
DAYS=""
PAST=""
FUTURE=""
CITY=""
LAT=""
LON=""
MATERIALIZE="false"
HOURS="0-23"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start) START="$2"; shift 2;;
    --days) DAYS="$2"; shift 2;;
    --past) PAST="$2"; shift 2;;
    --future) FUTURE="$2"; shift 2;;
    --city) CITY="$2"; shift 2;;
    --lat) LAT="$2"; shift 2;;
    --lon) LON="$2"; shift 2;;
    --hours) HOURS="$2"; shift 2;;
    --materialize) MATERIALIZE="true"; shift;;
    *) usage;;
  esac
done

if [[ -z "$START" || -z "$CITY" || -z "$LAT" || -z "$LON" || -z "$DAYS" || -z "$PAST" || -z "$FUTURE" ]]; then
  usage
fi

LOG_DIR="$(cd "$(dirname "$0")/.." && pwd)/logs"
mkdir -p "$LOG_DIR"
BACKEND_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if ! start_ts=$(date -jf "%Y-%m-%d" "$START" +%s 2>/dev/null); then
  echo "Invalid start date" >&2
  exit 1
fi

for ((i=0; i<${DAYS}; i++)); do
  current_date=$(date -jf %s $((start_ts + i*86400)) +%Y-%m-%d)
  log_file="$LOG_DIR/daily_sync_${current_date}.log"
  cmd=(python -m app.jobs.daily_sync \
    --city "$CITY" \
    --lat "$LAT" \
    --lon "$LON" \
    --past-days "$PAST" \
    --future-days "$FUTURE" \
    --hours "$HOURS" \
    --base-date "$current_date")
  if [[ "$MATERIALIZE" == "true" ]]; then
    cmd+=(--materialize)
  fi
  (
    cd "$BACKEND_DIR" && \
    DATABASE_URL="${DATABASE_URL:-}" "${cmd[@]}"
  ) | tee "$log_file"
done
