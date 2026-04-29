#!/bin/bash
# Start scheduler in background, then API in foreground
python main.py &
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
