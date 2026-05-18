#!/bin/bash
# Travel AI Agent — backend startup script

set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill in your Azure credentials."
  exit 1
fi

PORT="${PORT:-8002}"

echo ""
echo "  ✈  Travel AI Agent"
echo "  ─────────────────────────────────────────"
echo "  API:    http://0.0.0.0:${PORT}"
echo "  Docs:   http://localhost:${PORT}/docs"
echo "  Health: http://localhost:${PORT}/health"
echo "  Chaos:  POST http://localhost:${PORT}/chaos/toggle"
echo "  Trace:  GET  http://localhost:${PORT}/trace/{session_id}"
echo "  ─────────────────────────────────────────"
echo ""

uvicorn main:app --host 0.0.0.0 --port "${PORT}"
