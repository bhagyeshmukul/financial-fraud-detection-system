#!/bin/sh
# Start container API workers after the separate migration service has completed.
set -eu
# Migrations are a separate one-shot service; scaling API workers never repeats DDL.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-2}" --log-level info
