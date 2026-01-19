#!/bin/bash
# Dagster startup script
# Starts the Dagster webserver for pipeline orchestration

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

# Dagster configuration
export DAGSTER_HOME=${DAGSTER_HOME:-$PROJECT_DIR/.dagster}
export DAGSTER_PORT=${DAGSTER_PORT:-3000}

echo "Starting Dagster webserver..."
echo "Project: $PROJECT_DIR"
echo "Dagster UI: http://localhost:$DAGSTER_PORT"
echo ""

# Create .dagster directory if it doesn't exist
mkdir -p "$DAGSTER_HOME"

# Start Dagster dev server
exec dagster dev -f pipeline.py --host 0.0.0.0 --port "$DAGSTER_PORT"
