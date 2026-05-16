#!/bin/bash
# ============================================================
#  Lancement rapide de l'API FastAPI
# ============================================================
set -e

echo "🚀 Démarrage de l'API Text-to-SQL..."
echo "📍 API Docs : http://localhost:8000/docs"
echo ""

cd "$(dirname "$0")"

PYTHONPATH=. uvicorn app.api:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level info
