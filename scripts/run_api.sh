#!/bin/bash
# FastAPI startup script
# Ensures environment is set up correctly before starting the API server

set -e

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load environment variables if .env exists
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set default values
export POSTGRES_HOST=${POSTGRES_HOST:-localhost}
export POSTGRES_PORT=${POSTGRES_PORT:-5432}
export POSTGRES_DB=${POSTGRES_DB:-medical_warehouse}
export POSTGRES_USER=${POSTGRES_USER:-postgres}
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}

# API configuration
export API_HOST=${API_HOST:-0.0.0.0}
export API_PORT=${API_PORT:-8000}
export API_WORKERS=${API_WORKERS:-4}

echo "Starting Medical Telegram Warehouse API..."
echo "Host: $API_HOST"
echo "Port: $API_PORT"
echo "Workers: $API_WORKERS"
echo ""
echo "API Documentation: http://$API_HOST:$API_PORT/docs"
echo "Health Check: http://$API_HOST:$API_PORT/health"
echo ""

# Start uvicorn server
exec uvicorn api.main:app \
    --host "$API_HOST" \
    --port "$API_PORT" \
    --workers "$API_WORKERS" \
    --log-level info \
    --access-log
