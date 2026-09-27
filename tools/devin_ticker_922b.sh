#!/bin/bash
# 9/22 第2便：Devinを18時まで遊ばせない係。
#   tools/devin_1by1_922b.py を60秒ごとに1回叩くだけ。叩くたびに1歩進む（様子見 or 次を投げる）。
#   ・1本ずつ。前の1本が終わるまで次は投げない（叩かれる側がそう書いてある）。
#   ・止め方：status/.devin_922b_stop を作る。
#   ・保険：18:00を過ぎたら自分で終わる。二重起動しない。
#   ・触らないもの：オンデマンド購入・自動チャージ・請求（このスクリプトは一切触らない）。
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$HOME/Desktop/tamago-shinchoku" || exit 1
LOG="status/devin_922b_ticker.log"
LOCK="status/.devin_922b_ticker.lock"

# 二重起動よけ（30分以上古いロックは壊れたものとみなして奪う）
if [ -f "$LOCK" ]; then
  age=$(( $(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || echo 0) ))
  if [ "$age" -lt 1800 ]; then
    echo "$(date '+%F %T') 既に走っています（pid $(cat "$LOCK")）。何もしません。" >> "$LOG"
    exit 0
  fi
fi
echo $$ > "$LOCK"

echo "$(date '+%F %T') ▶ ticker開始（18:00まで60秒ごと）" >> "$LOG"
while true; do
  [ -f status/.devin_922b_stop ] && { echo "$(date '+%F %T') ■ 停止札があったので終わります" >> "$LOG"; break; }
  h=$(date +%H%M)
  [ "$h" -ge 1800 ] && { echo "$(date '+%F %T') ■ 18:00になったので終わります" >> "$LOG"; break; }
  echo "$(date '+%F %T') --" >> "$LOG"
  python3 tools/devin_1by1_922b.py >> "$LOG" 2>&1
  # 待ち行列が空になったら、これ以上叩いても意味がないので終わる
  if tail -3 "$LOG" | grep -q "待ち行列が空です"; then
    echo "$(date '+%F %T') ■ 待ち行列が空になったので終わります" >> "$LOG"
    break
  fi
  sleep 60
done
rm -f "$LOCK"
