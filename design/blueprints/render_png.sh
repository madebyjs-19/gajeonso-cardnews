#!/bin/bash
# 도면 SVG → assets/blueprints/<kind>_<theme>.png (2배 해상도, 투명 배경). macOS Google Chrome 필요.
# 사용: bash design/blueprints/render_png.sh   (저장소 최상위에서)
set -e
cd "$(dirname "$0")/../.."
python3 design/blueprints/build.py
CH="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
mkdir -p assets/blueprints
KINDS=$(python3 -c "import sys; sys.path.insert(0,'design/blueprints'); import build; print(' '.join(f'{k}:{build.D[k][1]}' for k in build.ORDER))")
for item in $KINDS; do
  k=${item%%:*}; o=${item##*:}
  if [ "$o" = "portrait" ]; then WS=440,960; else WS=900,360; fi
  for t in dark light orange; do
    "$CH" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 --default-background-color=00000000 \
      --window-size=$WS --virtual-time-budget=5000 --screenshot="assets/blueprints/${k}_${t}.png" \
      "file://$PWD/design/blueprints/export.html#kind=$k&t=$t" >/dev/null 2>&1
  done
done
ls assets/blueprints | wc -l
