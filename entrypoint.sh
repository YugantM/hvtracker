#!/bin/sh
set -e
chown -R hvt:hvt /data
exec gosu hvt uvicorn app:app --host 0.0.0.0 --port "${PORT:-8080}"
