#!/bin/sh

set -e
PY=".venv/bin/python -I -B"
$PY maps/mobile/scripts/30_build_html.py --pass1 | head -1
$PY maps/mobile/scripts/41_snapshot_fallback.py
$PY maps/mobile/scripts/30_build_html.py | grep -v '^sep_m'
