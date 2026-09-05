#!/bin/bash
# 工場の心臓。15秒おきに「軽い2つ」だけを回し続ける常駐プロセス。
#
# 2026-09-04 たまごさん「回り続ける仕組みにしたい」「1個空いたら1個繰り上がる、ところてんみたいに」
#
# なぜ常駐にしたか（実測に基づく）：
#   これまで着火と受信箱は、5分おきのlaunchd便（machine_status_push.sh）の中でしか動いていなかった。
#   ところがその便は1回に4〜5分かかる（重い計測 factory_status が27秒〜、走行が増えるとさらに伸びる）ので、
#   実際には**5〜14分に1回しか回っていなかった**。
#   実害：22:25に発車したあと22:32まで7分間、着火も受信箱も一度も動かず、
#         たまごさんがスマホで押したボタンが7分間Macに届かなかった。
#   → 重い計測は5分便のまま。軽い2つ（着火・受信箱）だけをここで15秒おきに回す。
#     どちらも1秒かからないので、Macの負荷はほぼ増えない。
#
# 二重起動しない。落ちても machine_status_push.sh が次の巡回で立て直す（自己修復）。
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$REPO/status/heartbeat.log"

echo "$(date '+%F %T') 心臓を起動しました" >> "$LOG"
while :; do
  python3 "$REPO/tools/auto_launcher.py"  >/dev/null 2>&1 || true
  python3 "$REPO/tools/command_ingest.py" >/dev/null 2>&1 || true
  # ログインが戻ったら自分で気づいて再開する（10分に1回だけ試す）
  python3 "$REPO/tools/auth_watch.py"     >/dev/null 2>&1 || true
  # 2026-09-05：中継所（進捗表→Mac）が死ぬと、たまごさんがボタンを押しても何も届かない。
  #   5分便まかせだと最大5分間ボタンが効かないままなので、心臓でも2分に1回見る。
  #   **投げっぱなしにして心臓は待たない**（対話待ちで工場を止めた07:03の事故の教訓）。
  RC="$REPO/status/.relay_check"
  if [ ! -f "$RC" ] || [ "$(( $(date +%s) - $(stat -f %m "$RC" 2>/dev/null || echo 0) ))" -ge 120 ]; then
    touch "$RC"
    ( bash "$REPO/tools/relay_up.sh" >/dev/null 2>&1 & ) >/dev/null 2>&1
  fi
  # ログが太らないように、たまに刈る
  if [ "$(( $(date +%s) % 3600 ))" -lt 20 ]; then
    tail -n 200 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null || true
    echo "$(date '+%F %T') 心臓は動いています" >> "$LOG"
  fi
  sleep 15
done
