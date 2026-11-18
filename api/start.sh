#!/bin/sh
# API container entry point: index the knowledge base, then serve.
set -e
python -m scripts.ingest_kb
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
