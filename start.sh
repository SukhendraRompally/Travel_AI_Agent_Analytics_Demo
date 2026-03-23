#!/bin/bash
# Expedia AI Travel Agent — Principal Product Builder Interview Demo
# Port 8002 (Typeface=8000, AsanaBot=8001)

set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill in your Azure credentials."
  exit 1
fi

echo ""
echo "  ✈  Expedia AI Travel Agent"
echo "  ─────────────────────────────────────────"
echo "  API:    http://0.0.0.0:8002"
echo "  Docs:   http://localhost:8002/docs"
echo "  Health: http://localhost:8002/health"
echo "  Chaos:  POST http://localhost:8002/chaos/toggle"
echo "  Trace:  GET  http://localhost:8002/trace/{session_id}"
echo "  ─────────────────────────────────────────"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8002 --reload
