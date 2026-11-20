#!/bin/sh
# Start a private PostgreSQL, fill the demo data, then serve the app on :7860.
# Data lives in /tmp, so every restart begins with a fresh demo.
set -e
export PGDATA=/tmp/pgdata
PG=/usr/lib/postgresql/bin

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  "$PG/initdb" -D "$PGDATA" -U helpdesk --auth=trust >/dev/null
fi
"$PG/pg_ctl" -D "$PGDATA" -o "-c listen_addresses=127.0.0.1 -p 5432 -k /tmp" -l /tmp/postgres.log -w start
"$PG/createdb" -h 127.0.0.1 -U helpdesk helpdesk 2>/dev/null || true

python -m scripts.ingest_kb
python -m scripts.seed_demo >/dev/null
echo "Demo data ready"

exec uvicorn serve:app --host 0.0.0.0 --port 7860
