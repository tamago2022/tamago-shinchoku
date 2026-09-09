#!/bin/bash
# 共通部品：現在の音量を読み、指定の増分（マイナス可）を足して設定する。
# 直接は呼ばない。volume_up.sh / volume_down.sh 等から呼ばれる。
set -euo pipefail
STEP="${1:-}"
if [[ -z "$STEP" ]]; then
  echo "内部エラー: 増分が指定されていません" >&2
  exit 1
fi
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CUR="$(osascript -e "output volume of (get volume settings)")"
NEXT=$(( CUR + STEP ))
if (( NEXT < 0 )); then NEXT=0; fi
if (( NEXT > 100 )); then NEXT=100; fi
bash "$HERE/volume_set.sh" "$NEXT"
echo "（変更前: ${CUR}）"
