#!/bin/bash
# 1065番：スマホ1画面（375px）の証拠を1枚だけ撮る。待たない・繰り返さない（長く眠る仕事は途中で落ちるため）。
set -u
REPO="$HOME/Desktop/tamago-shinchoku"
URL="https://tamago2022.github.io/tamago-shinchoku/share/check/1065-tekizai.html"
cd "$REPO" || exit 1
node tools/_825_screenshot_375.mjs "$URL" "$REPO/status/1065_tekizai_375.png" \
  >> "$REPO/status/1065_kakunin.txt" 2>&1
echo "$(date '+%F %T') 375pxの証拠 $REPO/status/1065_tekizai_375.png" >> "$REPO/status/1065_kakunin.txt"
