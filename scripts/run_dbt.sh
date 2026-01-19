#!/bin/bash
# Script to run dbt with environment variables loaded from .env

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment if it exists
if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
fi

# Load environment variables from .env file
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

# Navigate to dbt project
cd "$PROJECT_DIR/medical_warehouse"

# Set DBT_PROFILES_DIR to current directory so dbt uses profiles.yml here
# instead of looking in ~/.dbt/
export DBT_PROFILES_DIR="$PROJECT_DIR/medical_warehouse"

# Run dbt command with all arguments passed through
dbt "$@"
