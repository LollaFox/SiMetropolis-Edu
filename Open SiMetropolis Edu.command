#!/bin/sh

cd -- "$(dirname -- "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
    echo 'This copy of SiMetropolis Edu still needs to be set up.' >&2
    exit 1
fi
exec .venv/bin/python -B -m classroom launch
