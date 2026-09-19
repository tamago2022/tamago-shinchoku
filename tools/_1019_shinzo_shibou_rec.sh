#!/bin/bash
# 1019番：心臓が「5分おきに死ぬ」瞬間を現行犯で押さえる記録係。
# 何も殺さない・何も直さない。3秒おきに見て書くだけ。20分で自分から終わる。
# 出力：status/1019_shinzo_shibou.log
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO/status/1019_shinzo_shibou.log"
END=$(( $(date +%s) + 1200 ))
LAST=""
echo "$(date '+%F %T') ── 記録開始（20分） ──" >> "$OUT"
while [ "$(date +%s)" -lt "$END" ]; do
  PIDS="$(pgrep -f 'tools/heartbeat.sh' | tr '\n' ',' )"
  AGE=$(( $(date +%s) - $(stat -f %m "$REPO/status/.heartbeat_alive" 2>/dev/null || echo 0) ))
  if [ "$PIDS" != "$LAST" ] || [ "$AGE" -gt 20 ]; then
    LOAD="$(uptime | sed 's/.*averages*: //')"
    TOP="$(ps -eo pcpu,command -r 2>/dev/null | sed -n 2p | cut -c1-90)"
    echo "$(date '+%F %T') 心臓pid=[$PIDS] 鼓動=${AGE}秒前 load=$LOAD 最重量=$TOP" >> "$OUT"
    if [ -z "$PIDS" ] && [ -n "$LAST" ]; then
      echo "   ↑ 死んだ直後に走っていたもの:" >> "$OUT"
      ps -eo pid,pcpu,etime,command -r 2>/dev/null | sed -n '2,7p' | cut -c1-120 | sed 's/^/     /' >> "$OUT"
    fi
    LAST="$PIDS"
  fi
  sleep 3
done
echo "$(date '+%F %T') ── 記録終了 ──" >> "$OUT"
