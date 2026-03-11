#!/bin/bash
# LinkedIn Bot — Startup Script
# Usage:
#   ./run.sh        → Production mode (Gunicorn, 4 workers × 4 threads)
#   ./run.sh dev    → Development mode (Flask debug server)

set -e

# Activate virtualenv
source .venv/bin/activate

if [ "$1" = "dev" ]; then
    echo "🔧 Starting in DEVELOPMENT mode (Flask debug server)..."
    python app.py
else
    echo "🚀 Starting in PRODUCTION mode (Gunicorn, 4 workers × 4 threads)..."
    gunicorn \
        --bind 0.0.0.0:5001 \
        --workers 4 \
        --threads 4 \
        --timeout 120 \
        --access-logfile logs/access.log \
        --error-logfile logs/error.log \
        --log-level info \
        app:app
fi
