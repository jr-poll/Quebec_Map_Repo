#!/bin/sh

set -e
PY=".venv/bin/python -I -B"
M=maps/mobile

if [ ! -f $M/manifest_before.txt ]; then
  mkdir -p $M
  find . -path ./.venv -prune -o -type f -print0 | sort -z | xargs -0 shasum -a 256 > /tmp/qc_manifest_before.$$ 
  mv /tmp/qc_manifest_before.$$ $M/manifest_before.txt
fi

QC_REPRO=1 $PY $M/scripts/30_build_html.py | head -1
cmp $M/tmp/repro.html maps/Quebec_2026_Swing_Map_FINAL.html && echo "REPRO: byte-identical to FINAL"

$PY $M/scripts/39_static_check.py maps/Quebec_2026_Swing_Map_FINAL.html final
$PY $M/scripts/40_mobile_matrix.py --target maps/Quebec_2026_Swing_Map_FINAL.html --label final > $M/tmp/matrix_final.log 2>&1
tail -1 $M/tmp/matrix_final.log

sh $M/scripts/build_all.sh
$PY $M/scripts/39_static_check.py maps/Quebec_2026_Swing_Map_FINAL_mobile.html mobile

$PY $M/scripts/40_mobile_matrix.py --target maps/Quebec_2026_Swing_Map_FINAL_mobile.html --label mobile > $M/tmp/matrix_mobile.log 2>&1 \
  || { tail -40 $M/tmp/matrix_mobile.log; exit 1; }
tail -1 $M/tmp/matrix_mobile.log

if xcrun simctl help >/dev/null 2>&1; then
  echo "simctl available: run the simulator steps in MOBILE_VALIDATION.md §6.2"
else
  echo "iOS Simulator: not available (xcrun simctl missing) - skipped"
fi
mkdir -p $M/screens/ql_final $M/screens/ql_mobile
qlmanage -t -s 1000 -o $M/screens/ql_final/ maps/Quebec_2026_Swing_Map_FINAL.html >/dev/null 2>&1 || echo "qlmanage failed (final)"
qlmanage -t -s 1000 -o $M/screens/ql_mobile/ maps/Quebec_2026_Swing_Map_FINAL_mobile.html >/dev/null 2>&1 || echo "qlmanage failed (mobile)"
$PY $M/scripts/45_quicklook_check.py

$PY $M/scripts/42_desktop_regression.py > $M/tmp/desktop_regression.log 2>&1 || { tail -30 $M/tmp/desktop_regression.log; exit 1; }
tail -1 $M/tmp/desktop_regression.log
$PY $M/scripts/95_test_html.py > $M/tmp/desktop95.log 2>&1 || { tail -20 $M/tmp/desktop95.log; exit 1; }
tail -1 $M/tmp/desktop95.log

$PY $M/scripts/43_parity.py > $M/tmp/parity.log

$PY $M/scripts/44_manifest.py | tail -1
echo "ALL MOBILE CHECKS PASSED"
