#!/bin/sh
cd -- "$(dirname -- "$0")" || exit 1
exec sh classroom/mac_teacher.sh
