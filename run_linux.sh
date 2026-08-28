#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
exec python3 run_project_os.py "$@"
