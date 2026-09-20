#!/bin/bash
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$REPO/status/972_url200.txt"
exec >"$OUT" 2>&1
echo "== 200確認（気長に） $(date '+%F %T') =="
for i in $(seq 1 14); do
  C=$(curl -sS -o /dev/null -m 10 -w '%{http_code}' -L "https://tamago2022.github.io/tamago-shinchoku/972-okane-report.html" 2>/dev/null)
  echo "$(date '+%H:%M:%S')  $C"
  [ "$C" = "200" ] && { echo "★200になりました"; break; }
  sleep 35
done
echo "== おわり $(date '+%F %T') =="
