#!/bin/sh
# Start native services from any directory, after applying table migrations.
set -eu
task_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$task_root"
# Load optional local configuration without committing actual secrets.
if [ -f .env ]; then set -a; . ./.env; set +a; fi
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg2://fraud_local@127.0.0.1:55432/fraud_db}"
# Apply migrations once before request workers start.
(cd backend && ../scripts/python -m alembic upgrade head)
"$task_root/scripts/python" -m uvicorn app.main:app --host 127.0.0.1 --port "${API_PORT:-8000}" &
task_api_pid=$!
# Stop only the API child this script started when the frontend/terminal exits.
cleanup() { kill "$task_api_pid" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
cd frontend
npm run dev
