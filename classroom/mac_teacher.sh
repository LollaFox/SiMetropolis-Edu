#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
if [ ! -x .venv/bin/python ] || [ "${1:-}" = "setup" ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r classroom/requirements.txt
fi
if [ "${1:-}" = "setup" ]; then
  exit 0
fi
exec .venv/bin/python -B -m classroom launch
