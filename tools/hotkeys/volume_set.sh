#!/bin/bash
# ベッドホットキー：音量を指定の数字（0-100）にする
# 使い方: volume_set.sh 55
set -euo pipefail
N="${1:-}"
if [[ -z "$N" || ! "$N" =~ ^[0-9]+$ ]]; then
  echo "使い方: volume_set.sh <0-100の整数>" >&2
  exit 1
fi
if (( N < 0 )); then N=0; fi
if (( N > 100 )); then N=100; fi
osascript -e "set volume output volume $N"
echo "音量を ${N} にしました"
