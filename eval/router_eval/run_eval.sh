#!/bin/bash
# Load env vars from project root
cd /Users/tanayvenkata/dev/focus-group
set -a
source .env
set +a

cd eval/router_eval
# Default config, pass all args through
npx promptfoo eval -c promptfooconfig_unified_router.yaml "$@"
