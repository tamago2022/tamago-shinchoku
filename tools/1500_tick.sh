#!/bin/bash
# 1500番 枠番の1周回。launchd から60秒おきに呼ばれる。
# ★心臓(heartbeat.sh)に相乗りしない独立の線。心臓が死んでいてもDevinは発車する。
#   （2026-09-28 実測：心臓が止まり、oneshot/pending に3本の票が溜まったまま動かなかった）
cd "$(dirname "$0")/.." || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
LOG="status/1500_tick.log"
exec >>"$LOG" 2>&1
echo "--- $(date '+%F %T') tick"

# ① Mac側の窓口（サンドボックスからの票）を必ず流す。心臓が死んでいても流れる
timeout 250 python3 tools/oneshot_runner.py || echo "oneshot_runner rc=$?"

# ② 枠が空いたら発車（空振りは0円）
timeout 120 python3 tools/1500_wakuban.py || echo "wakuban rc=$?"

# ③ 成績表を付け直す（中で30分に1回に間引いている）
timeout 180 python3 tools/1501_devin_seiseki.py || echo "seiseki rc=$?"

# ④ 心臓が死んでいたら起こす（起きていれば何もしない）
if ! pgrep -f "tools/heartbeat.sh" >/dev/null 2>&1; then
  echo "心臓が止まっていたので起こす"
  nohup bash tools/heartbeat.sh >/dev/null 2>&1 &
fi

# ⑤ ログが太らないように尻を切る
tail -n 2000 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"
