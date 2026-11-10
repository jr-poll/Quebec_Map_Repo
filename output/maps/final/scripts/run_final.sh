#!/bin/sh

set -e
cd "$(dirname "$0")/../../.." || exit 1
PY=".venv/bin/python -I -B"
F=maps/final
$PY $F/colour_check.py
$PY $F/scripts/30_build_html.py
$PY $F/scripts/95_test_html.py
$PY $F/scripts/80_compare.py maps/Quebec_2026_Swing_Map.html maps/Quebec_2026_Swing_Map_FINAL.html --json $F/compare/html_diff.json
echo "ALL HTML STEPS PASSED"
