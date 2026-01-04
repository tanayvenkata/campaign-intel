#!/bin/bash
# Load env vars from project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"
set -a
source .env
set +a

cd "$SCRIPT_DIR"
# Default config, pass all args through
npx promptfoo eval -c promptfooconfig_unified_router.yaml "$@"
