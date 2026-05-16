#!/bin/bash
# ============================================================
#  Lancement rapide de l'interface Streamlit
# ============================================================
set -e

echo "🚀 Démarrage de Text-to-SQL Intelligent..."
echo "📍 Interface : http://localhost:8501"
echo ""

cd "$(dirname "$0")"

PYTHONPATH=. streamlit run app/main.py \
    --server.port=8501 \
    --server.address=localhost \
    --browser.gatherUsageStats=false \
    --theme.base=dark \
    --theme.primaryColor="#60a5fa" \
    --theme.backgroundColor="#0f1117" \
    --theme.secondaryBackgroundColor="#1e293b" \
    --theme.textColor="#e2e8f0"
