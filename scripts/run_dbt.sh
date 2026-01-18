#!/bin/bash
# Script to run dbt with environment variables loaded from .env

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment variables from .env file
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

# Navigate to dbt project
cd "$PROJECT_DIR/medical_warehouse"

# Run dbt command with all arguments passed through
dbt "$@"
