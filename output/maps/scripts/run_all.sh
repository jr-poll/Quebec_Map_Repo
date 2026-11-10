#!/bin/sh

set -e
cd "$(dirname "$0")/../.." || exit 1
PY=".venv/bin/python -I -B"
$PY maps/scripts/10_geometry.py
$PY maps/scripts/11_plan.py
$PY maps/scripts/12_validate_plan.py
$PY maps/scripts/30_build_html.py
$PY maps/scripts/95_test_html.py
