#!/usr/bin/env bash
# Macの負荷を1行で出す（止まらない工場の心臓・土台）。2026-09-16 作り直し。
#
# 消えていた経緯: 元は /Users/mac/Desktop/machine_load.sh だったが掃除のどこかで消え、
# tools/machine_status_push.sh と tools/factory_status.py の LOADSH がどちらも実体の無い
# パスを指し続けていた（status/failures.md 参照）。二度と消えないようリポジトリの中に置く。
#
# 出力形式（factory_status.py / machine_status_push.sh のパース部がこの形を前提にしている。変えない）:
#   負荷 12% ｜ CPU 9% / メモリ圧迫 58% / スワップ 0.20GB / ディスク空き 61GB ｜ 稼働 14本 ｜ あと3本OK
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
CAP=4  # 常時運用の目安上限（factory_status.pyのSAFE_FLOORと同じ4）。実際の安全本数はfactory_status.pyが別途計算する

CORES=$(sysctl -n hw.ncpu 2>/dev/null || echo 8)
LOAD1=$(sysctl -n vm.loadavg 2>/dev/null | awk '{print $2}')
LOAD1=${LOAD1:-0}
LOAD_PCT=$(awk -v l="$LOAD1" -v c="$CORES" 'BEGIN{printf "%d", (l/c)*100}')

# top -l 1 は高負荷時に数秒〜十数秒かかり計測失敗の原因になるため使わない（実測: loadavg 200超で18秒）。psは高負荷時でも高速
CPU_PCT=$(ps -A -o %cpu= 2>/dev/null | awk -v c="$CORES" '{s+=$1} END{printf "%d", (s/c<100?s/c:100)}')
CPU_PCT=${CPU_PCT:-0}

FREE_PCT=$(memory_pressure 2>/dev/null | grep "System-wide memory free percentage" | grep -oE '[0-9]+' || echo "")
if [ -n "$FREE_PCT" ]; then
  MEM_PCT=$((100 - FREE_PCT))
else
  MEM_PCT=0
fi

SWAP_USED_MB=$(sysctl vm.swapusage 2>/dev/null | sed -E 's/.*used = ([0-9.]+)M.*/\1/')
SWAP_GB=$(awk -v m="${SWAP_USED_MB:-0}" 'BEGIN{printf "%.2f", m/1024}')

# 2026-09-20（968番）★測る場所を直した。
#   それまで `df -g /` を見ていた。このMacの / は「macOS Sonoma」システムボリュームで、
#   本当の置き場所である Data ボリューム(/System/Volumes/Data)とは空きが全く違う。
#   実測 2026-09-20 03:04：`df / `→270GB、`df /System/Volumes/Data`→114GB。
#   ＝machine.json も進捗表も**156GB多い嘘の数字**を出し続けていた（実測「ディスク空き 252GB」）。
#   Data ボリュームには 500GB の quota がかかっており(diskutil apfs list で確認)、
#   工場が実際に書けるのはそちらの空き。disk_guardian.py も同じ場所を見ている（数字が一致する）。
DISK_FREE_GB=$(df -g /System/Volumes/Data 2>/dev/null | awk 'NR==2{print $4}')
DISK_FREE_GB=${DISK_FREE_GB:-0}

SESS=$(python3 -c "
import json
try:
    items = json.load(open('$REPO/status/queue.json', encoding='utf-8')).get('items') or []
    print(sum(1 for x in items if x.get('status') == 'running'))
except Exception:
    print(0)
" 2>/dev/null || echo 0)

if [ "$SESS" -gt "$CAP" ]; then
  NOTE="$((SESS - CAP))本超過（畳め）"
else
  NOTE="あと$((CAP - SESS))本OK"
fi

echo "負荷 ${LOAD_PCT}% ｜ CPU ${CPU_PCT}% / メモリ圧迫 ${MEM_PCT}% / スワップ ${SWAP_GB}GB / ディスク空き ${DISK_FREE_GB}GB ｜ 稼働 ${SESS}本 ｜ ${NOTE}"
