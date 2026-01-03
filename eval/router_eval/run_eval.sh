#!/bin/bash
cd /Users/tanayvenkata/dev/focus-group
set -a
source .env
set +a
cd eval/router_eval
npx promptfoo eval "$@"
