#!/bin/sh
# An isolated local Postgres; never reconfigures an existing database service.
set -eu
task_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
pg_bin="${POSTGRES_BIN:-/Library/PostgreSQL/17/bin}"
task_data="$task_root/.runtime/postgres"
task_port="${LOCAL_POSTGRES_PORT:-55432}"
if [ ! -x "$pg_bin/pg_ctl" ]; then
  echo "Set POSTGRES_BIN to your PostgreSQL bin directory, or use docker compose." >&2
  exit 1
fi
mkdir -p "$task_root/.runtime"
if [ "${1:-start}" = "stop" ]; then
  exec "$pg_bin/pg_ctl" -D "$task_data" stop -m fast
fi
# Initialize only a missing project cluster; preserve an existing database.
if [ ! -f "$task_data/PG_VERSION" ]; then
  "$pg_bin/initdb" -D "$task_data" -A trust -U fraud_local --encoding=UTF8 --no-locale
fi
if ! "$pg_bin/pg_ctl" -D "$task_data" status >/dev/null 2>&1; then
  "$pg_bin/pg_ctl" -D "$task_data" -l "$task_root/.runtime/postgres.log" -o "-h 127.0.0.1 -p $task_port" start
fi
# Keep application records and destructive test transactions in separate databases.
for task_database in fraud_db fraud_test; do
  if ! "$pg_bin/psql" -h 127.0.0.1 -p "$task_port" -U fraud_local -d postgres -Atc "SELECT datname FROM pg_database" | grep -Fx "$task_database" >/dev/null; then
    "$pg_bin/createdb" -h 127.0.0.1 -p "$task_port" -U fraud_local "$task_database"
  fi
done
echo "Local database: postgresql+psycopg2://fraud_local@127.0.0.1:$task_port/fraud_db"
